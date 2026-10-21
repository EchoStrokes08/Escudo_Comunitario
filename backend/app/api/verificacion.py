"""
Verificación pública de certificados y auditoría de la cadena.

  GET  /api/verificar/{codigo}               ¿El reporte existe y está íntegro? (hash completo o prefijo)
  GET  /api/verificar/{hash}/registro.json   JSON canónico del bloque (su SHA-256 = certificado)
  GET  /api/verificar/{hash}/prueba.ots      Prueba OpenTimestamps (verificable en opentimestamps.org)
  GET  /api/cadena/estado                    Altura y último hash de la cadena
  GET  /api/cadena/auditoria                 Recalcula TODOS los hashes y enlaces
  POST /api/cadena/sellar/{hash}             Sella el bloque en Bitcoin (público, idempotente)
  POST /api/cadena/anclar-pendientes         Reintenta anclar bloques sin sello (requiere token)
"""
from fastapi import APIRouter, Header, HTTPException, Request, Response

from app.core.config import settings
from app.core.limite import limitar_por_ip
from app.services import firebase_db
from app.services.procesamiento import sellar
from app.services.registro import (
    CAMPOS_BLOQUE, GENESIS, anclar_opentimestamps, archivo_ots, canonico, verificar_bloque, verificar_cadena,
)

router = APIRouter()


def _bloque_o_404(codigo: str) -> dict:
    codigo = "".join(c for c in codigo.lower() if c in "0123456789abcdef")
    if len(codigo) < 12:
        raise HTTPException(status_code=400, detail="El código del certificado debe tener al menos 12 caracteres.")
    bloque = firebase_db.buscar_bloque(codigo)
    if not bloque:
        raise HTTPException(status_code=404, detail="No encontramos ese certificado en el registro.")
    return bloque


@router.get("/verificar/{codigo}")
def verificar(codigo: str):
    bloque = _bloque_o_404(codigo)
    h = bloque["hash"]
    integro = verificar_bloque(h, bloque)

    if bloque["altura"] == 0:
        anterior_ok = bloque.get("prev") == GENESIS
    else:
        anterior = firebase_db.obtener_bloque(bloque["prev"])
        anterior_ok = bool(anterior) and verificar_bloque(anterior["hash"], anterior)
    siguiente = firebase_db.bloque_siguiente(h)

    anclaje = bloque.get("anclaje") or {}
    publico = firebase_db.obtener_publico(h) or {}
    return {
        "encontrado": True,
        "integro": integro,
        "certificado": h,
        "bloque": {k: bloque[k] for k in CAMPOS_BLOQUE if k in bloque},
        "enlaces": {
            "anterior": bloque.get("prev"),
            "anterior_valido": anterior_ok,
            "siguiente": siguiente["hash"] if siguiente else None,
            "siguiente_apunta_aqui": bool(siguiente) and siguiente.get("prev") == h,
        },
        "anclaje": {
            "estado": anclaje.get("estado", "sin_anclar"),
            "calendario": anclaje.get("calendario"),
            "fecha": anclaje.get("fecha"),
            "descargable": bool(anclaje.get("prueba_b64")),
        },
        "reporte": {
            "upz": publico.get("upz"),
            "tipo_fraude": publico.get("tipo_fraude"),
            "mensaje_anonimizado": publico.get("mensaje_anonimizado"),
            "resumen": publico.get("resumen"),
            "hallazgos": publico.get("hallazgos", []),
        },
        "url": f"{settings.APP_URL}/verificar/{h}",
    }


@router.get("/verificar/{codigo}/registro.json")
def descargar_registro(codigo: str):
    bloque = _bloque_o_404(codigo)
    return Response(
        content=canonico(bloque), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="registro-{bloque["hash"][:16]}.json"'},
    )


@router.get("/verificar/{codigo}/prueba.ots")
def descargar_ots(codigo: str):
    bloque = _bloque_o_404(codigo)
    prueba = (bloque.get("anclaje") or {}).get("prueba_b64")
    if not prueba:
        raise HTTPException(status_code=404, detail="Este bloque aún no tiene prueba de OpenTimestamps.")
    return Response(
        content=archivo_ots(bloque["hash"], prueba), media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="registro-{bloque["hash"][:16]}.json.ots"'},
    )


@router.get("/cadena/estado")
def estado_cadena():
    estado = firebase_db.estado_cadena()
    return {"bloques": estado.get("altura", -1) + 1, "ultimo_hash": estado.get("ultimo_hash"),
            "actualizado": estado.get("actualizado")}


@router.get("/cadena/auditoria")
def auditoria():
    bloques = firebase_db.bloques_ordenados()
    resultado = verificar_cadena(bloques)
    anclados = sum(1 for b in bloques if (b.get("anclaje") or {}).get("prueba_b64"))
    return {**resultado, "anclados": anclados,
            "ultimo_hash": bloques[-1]["hash"] if bloques else None}


@router.post("/cadena/sellar/{codigo}")
async def sellar_bloque(codigo: str, request: Request):
    """
    Sella un bloque en Bitcoin (OpenTimestamps). Público e idempotente: el frontend lo llama
    justo después de mostrar el veredicto para que la persona no espere los ~2 s del sello.
    """
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    limitar_por_ip(f"sello:{ip}")
    bloque = _bloque_o_404(codigo)
    anclaje = bloque.get("anclaje") or {}
    if not anclaje.get("prueba_b64"):
        anclaje = await sellar(bloque["hash"])
    return {"certificado": bloque["hash"], "estado": anclaje.get("estado"), "calendario": anclaje.get("calendario")}


@router.post("/cadena/anclar-pendientes")
async def anclar_pendientes(authorization: str = Header("")):
    if not settings.AUTORIDADES_TOKEN or authorization != f"Bearer {settings.AUTORIDADES_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")
    anclados = 0
    for h in firebase_db.bloques_sin_anclar():
        anclaje = await anclar_opentimestamps(h)
        firebase_db.guardar_anclaje(h, anclaje)
        anclados += anclaje.get("estado") == "pendiente_bitcoin"
    return {"anclados": anclados}
