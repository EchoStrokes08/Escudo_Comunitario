"""
Flujo único de un reporte, compartido por el canal web y WhatsApp:

  1. Agente IA multimodal (texto, capturas, PDF, notas de voz)  ─┐ en paralelo
  2. Verificación en fuentes abiertas del texto escrito          ─┘
  3. Segunda verificación con lo que la IA leyó en los adjuntos
  4. Riesgo + confianza explicables, tipo de fraude y plan de acción
  5. Bloque encadenado (certificado) + versiones privada y pública
  6. Anclaje en Bitcoin vía OpenTimestamps
  7. Historial comunitario de indicadores y detección de brotes por UPZ
"""
import asyncio
import logging

from app.core.config import settings
from app.services import firebase_db
from app.services.alertas_comunitarias import detectar_brote, emitir_alerta
from app.services.analizador import evaluar_fraude
from app.services.anonimizar import anonimizar_texto, enmascarar, generalizar_ubicacion
from app.services.orientacion import nombre_tipo, plan_accion
from app.services.puntuacion import calcular
from app.services.registro import anclar_opentimestamps
from app.services.verificador import claves_indicadores, verificar_mensaje

log = logging.getLogger("escudo.procesamiento")


def _fusionar_verificaciones(a: dict, b: dict) -> dict:
    """Une la verificación del texto con la de los indicadores leídos en adjuntos."""
    vistos = {(h["tipo"], h["valor"], h["fuente"]) for h in a["hallazgos"]}
    extra = [h for h in b["hallazgos"] if (h["tipo"], h["valor"], h["fuente"]) not in vistos]
    fuentes = {f["nombre"]: f["estado"] for f in a["fuentes"]}
    for f in b["fuentes"]:
        if fuentes.get(f["nombre"]) != "consultada":
            fuentes[f["nombre"]] = f["estado"]
    comunidad = {(c["tipo"], c["valor"]): c for c in a["comunidad"] + b["comunidad"]}
    hallazgos = a["hallazgos"] + extra
    return {
        **b,
        "urls": list(dict.fromkeys(a["urls"] + b["urls"])),
        "dominios": list(dict.fromkeys(a["dominios"] + b["dominios"])),
        "cuentas": list({c["valor"]: c for c in a["cuentas"] + b["cuentas"]}.values()),
        "telefonos": list(dict.fromkeys(a["telefonos"] + b["telefonos"])),
        "indicadores": list(dict.fromkeys(a["indicadores"] + b["indicadores"])),
        "hallazgos": hallazgos,
        "coincidencias": len(hallazgos),
        "coincidencias_reales": len([h for h in hallazgos if not h.get("simulada")]),
        "comunidad": list(comunidad.values()),
        "arriesgado": a["arriesgado"] or b["arriesgado"],
        "fuentes": [{"nombre": n, "estado": e} for n, e in fuentes.items()],
    }


def _historial(claves):
    try:
        return firebase_db.consultar_indicadores(claves)
    except Exception as error:
        log.warning("No se pudo consultar el historial comunitario: %s", error)
        raise


# Presupuestos de tiempo (s) para WhatsApp: Twilio abandona el webhook a los 15 s
_RAPIDO = {"llm": 8.5, "red": 2.5}


async def sellar(certificado: str, timeout: float | None = None) -> dict:
    """
    Ancla el bloque en Bitcoin vía OpenTimestamps (~2 s). No bloquea la respuesta al
    ciudadano: el frontend lo pide justo después de mostrar el veredicto
    (POST /api/cadena/sellar/{hash}). Mientras tanto el bloque ya está protegido por la
    cadena de hashes, y cualquier sello posterior de la cadena lo cubre también.
    """
    anclaje = await anclar_opentimestamps(certificado, timeout=timeout)
    try:
        firebase_db.guardar_anclaje(certificado, anclaje)
    except Exception as error:
        log.warning("No se pudo guardar el anclaje: %s", error)
    return anclaje


async def revisar_brote(upz: str | None, tipo: str, nivel: str) -> dict | None:
    """
    Detecta y emite la alerta temprana de la UPZ (sin bloquear si falla). Se llama al
    registrar el reporte y, en los chats, cuando la persona responde su UPZ después.
    """
    if not upz or nivel == "bajo":
        return None
    try:
        alerta = await asyncio.to_thread(detectar_brote, upz, tipo)
    except Exception as error:
        log.warning("No se pudo revisar brotes: %s", error)
        return None
    if not alerta:
        return None
    try:
        return await emitir_alerta(alerta)
    except Exception as error:
        log.warning("No se pudo emitir la alerta comunitaria: %s", error)
        return alerta


async def analizar(mensaje: str, adjuntos: list[dict], *, rapido: bool = False, historial=_historial) -> dict:
    """
    Pasos 1-4 del flujo, sin escribir nada: IA + fuentes abiertas + riesgo, confianza y plan.
    Lo usan procesar_reporte y el script de evaluación (scripts/evaluar.py).
    """
    t = _RAPIDO if rapido else {"llm": None, "red": None}

    # 1-2. IA y verificación del texto escrito, en paralelo
    analisis, verif_texto = await asyncio.gather(
        evaluar_fraude(mensaje, adjuntos, presupuesto=t["llm"]),
        verificar_mensaje(mensaje, historial=historial, timeout_red=t["red"]),
    )

    # 3. Lo que la IA leyó en capturas/PDF/audio también se verifica, solo si trae indicadores nuevos
    leido = analisis.get("texto_detectado", "")
    extra = analisis.get("indicadores") or {}
    nuevos = set(claves_indicadores(leido, extra)) - set(verif_texto["indicadores"])
    if nuevos:
        verif_adjuntos = await verificar_mensaje(leido, indicadores_extra=extra, historial=historial,
                                                 timeout_red=t["red"])
        verificacion = _fusionar_verificaciones(verif_texto, verif_adjuntos)
    else:
        verificacion = verif_texto

    # 4. Riesgo, confianza y orientación
    puntaje = calcular(analisis, verificacion, mensaje, adjuntos)
    tipo = analisis["tipo_fraude"]
    if puntaje["nivel_riesgo"] < 25:
        tipo = "legitimo"
    elif tipo == "legitimo" and puntaje["nivel"] != "bajo":
        tipo = "otro"  # las fuentes abiertas subieron el riesgo aunque la IA no vio fraude
    return {"analisis": analisis, "verificacion": verificacion, "puntaje": puntaje, "tipo": tipo,
            "plan": plan_accion(tipo, puntaje["nivel_riesgo"]), "leido": leido}


async def procesar_reporte(*, mensaje: str, adjuntos: list[dict], canal: str, reportante: str,
                           upz: str | None, lat: float | None, lng: float | None,
                           rapido: bool = False) -> dict:
    r = await analizar(mensaje, adjuntos, rapido=rapido)
    analisis, verificacion, puntaje = r["analisis"], r["verificacion"], r["puntaje"]
    tipo, plan, leido = r["tipo"], r["plan"], r["leido"]
    flags = analisis["flags"]
    resumen = analisis["resumen"]

    indicadores = verificacion["indicadores"]  # [(tipo, valor)]
    comunidad_publica = [{"tipo": c["tipo"], "valor": enmascarar(c["valor"]), "veces": c["veces"]}
                         for c in verificacion["comunidad"]]
    hallazgos_publicos = [
        {**{k: v for k, v in h.items() if k != "valor"}, "valor": enmascarar(h["valor"])}
        for h in verificacion["hallazgos"]
    ]
    adjuntos_meta = [{"nombre": a["nombre"], "mime": a["mime"], "tamano": a["tamano"], "sha256": a["sha256"]}
                     for a in adjuntos]
    lat_pub, lng_pub = generalizar_ubicacion(lat, lng)

    analisis_bloque = {
        "nivel_riesgo": puntaje["nivel_riesgo"], "confianza": puntaje["confianza"],
        "tipo_fraude": tipo, "flags": flags, "motor": analisis.get("motor", ""),
    }
    verificacion_guardada = {k: v for k, v in verificacion.items() if k != "indicadores"}

    privado = {
        "mensaje_original": mensaje,
        "texto_detectado": leido,
        "nivel_riesgo": puntaje["nivel_riesgo"],
        "confianza": puntaje["confianza"],
        "tipo_fraude": tipo,
        "entidad_suplantada": analisis.get("entidad_suplantada", ""),
        "flags": flags,
        "resumen": resumen,
        "verificacion": verificacion_guardada,
        "indicadores": [{"tipo": t, "valor": v} for t, v in indicadores],
        "motor": analisis.get("motor", ""),
        "modelo": analisis.get("modelo"),
        "upz": upz, "lat": lat, "lng": lng,
        "adjuntos": adjuntos_meta,
        "estado": "registrado",
    }
    publico = {
        "mensaje_anonimizado": anonimizar_texto(mensaje or leido),
        "nivel_riesgo": puntaje["nivel_riesgo"],
        "confianza": puntaje["confianza"],
        "tipo_fraude": tipo,
        "entidad_suplantada": analisis.get("entidad_suplantada", ""),
        "flags": flags,
        "resumen": anonimizar_texto(resumen, 400),
        "hallazgos": hallazgos_publicos,
        "indicadores": [{"tipo": t, "valor": enmascarar(v)} for t, v in indicadores],
        "comunidad": comunidad_publica,
        "upz": upz, "lat": lat_pub, "lng": lng_pub,
        "adjuntos": len(adjuntos),
        "con_audio": any(a["mime"].startswith("audio/") for a in adjuntos),
        "motor": "ia" if analisis.get("motor") == "llm" else "local",
        "anclaje": "en_proceso",
    }

    # 5. Bloque encadenado + privado + público (transacción)
    bloque = firebase_db.registrar_reporte(
        canal=canal, reportante=reportante, mensaje=mensaje, adjuntos=adjuntos,
        analisis=analisis_bloque, privado=privado, publico=publico,
    )
    certificado = bloque["hash"]

    # 6. Historial comunitario y brotes, en paralelo y sin bloquear si fallan.
    #    El sello en Bitcoin se pide después (sellar), para no hacer esperar a la persona.
    def _indicadores():
        try:
            firebase_db.incrementar_indicadores(indicadores, upz, certificado)
        except Exception as error:
            log.warning("No se pudo actualizar indicadores: %s", error)

    _, alerta = await asyncio.gather(asyncio.to_thread(_indicadores),
                                     revisar_brote(upz, tipo, puntaje["nivel"]))
    anclaje = {"estado": "en_proceso"}

    return {
        "id": certificado,
        "certificado": certificado,
        "altura": bloque["altura"],
        "prev": bloque["prev"],
        "fecha": bloque["fecha"],
        "hash_mensaje": bloque["hash_mensaje"],
        "url_certificado": f"{settings.APP_URL}/certificado/{certificado}",
        "url_verificacion": f"{settings.APP_URL}/verificar/{certificado}",
        "anclaje": {k: v for k, v in anclaje.items() if k != "prueba_b64"},
        "nivel_riesgo": puntaje["nivel_riesgo"],
        "nivel": puntaje["nivel"],
        "confianza": puntaje["confianza"],
        "nivel_confianza": puntaje["nivel_confianza"],
        "factores_confianza": puntaje["factores"],
        "tipo_fraude": {"id": tipo, "nombre": nombre_tipo(tipo)},
        "entidad_suplantada": analisis.get("entidad_suplantada", ""),
        "flags": flags,
        "resumen": resumen,
        "plan_accion": plan,
        "texto_detectado": leido,
        "verificacion": {k: v for k, v in verificacion_guardada.items()},
        "comunidad": verificacion["comunidad"],
        "motor": analisis.get("motor", ""),
        "modelo": analisis.get("modelo"),
        "alerta_comunitaria": alerta,
        "adjuntos_analizados": len(adjuntos),
        "adjuntos": adjuntos_meta,
    }
