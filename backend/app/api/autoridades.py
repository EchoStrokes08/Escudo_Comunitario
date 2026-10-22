"""
Vista para autoridades y organizaciones comunitarias (Policía, Fiscalía, JAC).

Todas las rutas exigen  Authorization: Bearer <AUTORIDADES_TOKEN>

  GET  /api/autoridades/casos[?formato=csv]          Casos completos (con su estado)
  POST /api/autoridades/casos/{codigo}/estado        Cambia el estado del caso: nuevo bloque encadenado
  GET  /api/autoridades/agrupados                    Indicadores con varias víctimas (un caso, N reportes)
  GET  /api/autoridades/indicador/{id}/evidencia     Paquete de evidencia de un indicador (JSON)
  GET  /api/autoridades/resumen                      Casos por estado y retroalimentación de las personas

Entrega los casos completos (mensaje original, indicadores sin enmascarar,
certificado) para investigar y actuar de forma coordinada. Nunca incluye el
teléfono de la víctima: solo su seudónimo.
"""
import csv
import io
import json
from collections import Counter

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services import firebase_db
from app.services.anonimizar import anonimizar_texto
from app.services.orientacion import nombre_tipo
from app.services.procesamiento import sellar
from app.services.registro import ESTADOS_CASO, es_seguimiento
from app.services.seguimiento import linea_de_tiempo, notificar_avance

from app.api.verificacion import _bloque_o_404

router = APIRouter()

_COLUMNAS = ["fecha", "certificado", "altura", "canal", "upz", "estado", "nivel_riesgo", "confianza", "tipo_fraude",
             "entidad_suplantada", "indicadores", "mensaje_original", "texto_detectado", "reportante", "motor"]


def _autorizar(authorization: str):
    if not settings.AUTORIDADES_TOKEN:
        raise HTTPException(status_code=503, detail="La vista de autoridades no está configurada (AUTORIDADES_TOKEN).")
    if authorization != f"Bearer {settings.AUTORIDADES_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")


def _sin_telefono(casos: list[dict]) -> list[dict]:
    # Los documentos anteriores a la v2 podían guardar el teléfono: nunca se exporta
    for caso in casos:
        caso.pop("telefono", None)
        caso.setdefault("estado", "registrado")
    return casos


@router.get("/autoridades/casos")
def casos(formato: str = "json", limite: int = 500, authorization: str = Header("")):
    _autorizar(authorization)
    casos = _sin_telefono(firebase_db.casos_completos(min(max(limite, 1), 2000)))

    if formato == "csv":
        salida = io.StringIO()
        escritor = csv.DictWriter(salida, fieldnames=_COLUMNAS, extrasaction="ignore")
        escritor.writeheader()
        for caso in casos:
            fila = dict(caso)
            fila["indicadores"] = "; ".join(f"{i.get('tipo')}:{i.get('valor')}" for i in caso.get("indicadores", []))
            escritor.writerow(fila)
        return Response(
            content="﻿" + salida.getvalue(), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="casos-escudo-comunitario.csv"'},
        )
    return {"total": len(casos), "casos": casos, "estados": ESTADOS_CASO}


class CambioEstado(BaseModel):
    estado: str = Field(..., description="en_revision | remitido | en_investigacion | cerrado")
    actor: str = Field(..., min_length=2, max_length=80, description="Quién actúa, ej. 'CAI Bosa Centro'")
    nota: str = Field("", max_length=500, description="Mensaje PÚBLICO para la víctima (se anonimiza)")


@router.post("/autoridades/casos/{codigo}/estado")
async def cambiar_estado(codigo: str, cambio: CambioEstado, authorization: str = Header("")):
    """
    Cada cambio de estado es un bloque nuevo de la cadena que apunta al certificado del
    reporte y se sella en Bitcoin: el historial del caso tampoco se puede reescribir.
    """
    _autorizar(authorization)
    if cambio.estado not in ESTADOS_CASO or cambio.estado == "registrado":
        raise HTTPException(status_code=400, detail=f"Estado inválido. Usa uno de: "
                                                    f"{', '.join(e for e in ESTADOS_CASO if e != 'registrado')}.")
    bloque = _bloque_o_404(codigo)
    if es_seguimiento(bloque):
        raise HTTPException(status_code=400, detail="Ese código es de un seguimiento; usa el certificado del reporte.")
    privado = firebase_db.obtener_privado(bloque["hash"])
    if privado is None:
        raise HTTPException(status_code=404, detail="El caso no existe en la base privada.")
    if privado.get("estado", "registrado") == cambio.estado:
        raise HTTPException(status_code=409, detail="El caso ya está en ese estado.")

    nuevo = firebase_db.registrar_seguimiento(
        caso=bloque["hash"], estado=cambio.estado, actor=" ".join(cambio.actor.split()),
        nota=anonimizar_texto(cambio.nota, 500),
    )
    anclaje = await sellar(nuevo["hash"], timeout=2.5)
    tiempo = linea_de_tiempo(bloque)
    avisados = await notificar_avance(bloque["hash"], tiempo[-1])
    return {
        "certificado_seguimiento": nuevo["hash"],
        "altura": nuevo["altura"],
        "anclaje": anclaje.get("estado"),
        "victimas_avisadas": avisados,
        "seguimiento": tiempo,
    }


@router.get("/autoridades/agrupados")
def agrupados(minimo: int = 2, authorization: str = Header("")):
    """
    Un mismo dominio, cuenta o teléfono reportado por varias personas es UN caso con
    varias víctimas: lo que la Fiscalía necesita para priorizar.
    """
    _autorizar(authorization)
    grupos = []
    for ind in firebase_db.indicadores_reincidentes(max(minimo, 2)):
        grupos.append({
            "id": ind["id"], "tipo": ind.get("tipo"), "valor": ind.get("valor"),
            "veces": int(ind.get("veces", 0)), "upz": sorted(u for u in ind.get("upz", []) if u),
            "certificados": ind.get("certificados", [])[-50:], "ultima": ind.get("ultima"),
        })
    return {"total": len(grupos), "grupos": grupos}


@router.get("/autoridades/indicador/{id_indicador}/evidencia")
def evidencia(id_indicador: str, authorization: str = Header("")):
    """Paquete de evidencia: todos los casos de un indicador con su certificado verificable."""
    _autorizar(authorization)
    ind = firebase_db.obtener_indicador(id_indicador)
    if not ind:
        raise HTTPException(status_code=404, detail="Indicador no encontrado.")
    casos = _sin_telefono(firebase_db.casos_por_certificados(ind.get("certificados", [])))
    casos.sort(key=lambda c: c.get("fecha", ""))
    paquete = {
        "titulo": f"Paquete de evidencia · {ind.get('tipo')} {ind.get('valor')}",
        "generado": firebase_db.ahora_iso(),
        "indicador": {"tipo": ind.get("tipo"), "valor": ind.get("valor"), "veces": ind.get("veces"),
                      "upz": sorted(u for u in ind.get("upz", []) if u)},
        "resumen": {
            "victimas_distintas": len({c.get("reportante") for c in casos}),
            "primera_fecha": casos[0].get("fecha") if casos else None,
            "ultima_fecha": casos[-1].get("fecha") if casos else None,
            "tipos_fraude": dict(Counter(nombre_tipo(c.get("tipo_fraude", "otro")) for c in casos)),
            "entidades_suplantadas": dict(Counter(c["entidad_suplantada"] for c in casos if c.get("entidad_suplantada"))),
        },
        "casos": [{
            "certificado": c.get("certificado") or c["id"],
            "verificacion": f"{settings.APP_URL}/verificar/{c.get('certificado') or c['id']}",
            "fecha": c.get("fecha"), "canal": c.get("canal"), "upz": c.get("upz"), "estado": c.get("estado"),
            "nivel_riesgo": c.get("nivel_riesgo"), "tipo_fraude": c.get("tipo_fraude"),
            "entidad_suplantada": c.get("entidad_suplantada"), "mensaje_original": c.get("mensaje_original"),
            "texto_detectado": c.get("texto_detectado"), "indicadores": c.get("indicadores", []),
            "fuentes_consultadas": (c.get("verificacion") or {}).get("fuentes", []),
            "hallazgos": (c.get("verificacion") or {}).get("hallazgos", []),
            "reportante": c.get("reportante"),
        } for c in casos],
        "como_verificar": "Cada certificado es el SHA-256 de un bloque encadenado y sellado en Bitcoin "
                          "(OpenTimestamps). Ábralo en la URL de verificación o descargue registro.json y prueba.ots.",
    }
    nombre = f"evidencia-{ind.get('tipo')}-{str(ind.get('valor'))[:24]}".replace("/", "-").replace(" ", "")
    return Response(
        content=json.dumps(paquete, ensure_ascii=False, indent=2), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.json"'},
    )


@router.get("/autoridades/resumen")
def resumen(authorization: str = Header("")):
    """Casos por estado y qué tan útil le pareció el análisis a la gente (y cuántos falsos positivos reportó)."""
    _autorizar(authorization)
    casos = firebase_db.casos_completos(2000)
    opiniones = firebase_db.retroalimentaciones()
    utiles = [o["util"] for o in opiniones if o.get("util") is not None]
    marcadas = [o for o in opiniones if o.get("era_legitimo")]
    return {
        "casos": len(casos),
        "por_estado": dict(Counter(c.get("estado", "registrado") for c in casos)),
        "retroalimentacion": {
            "respuestas": len(opiniones),
            "util_pct": round(100 * sum(utiles) / len(utiles)) if utiles else None,
            "marcados_legitimos": len(marcadas),
        },
    }
