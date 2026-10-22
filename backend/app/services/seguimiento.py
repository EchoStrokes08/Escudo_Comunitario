"""
Seguimiento del caso: línea de tiempo verificable y avisos a la víctima.

La línea de tiempo empieza en el bloque del reporte ("registrado") y sigue con
cada bloque de seguimiento encadenado (en revisión, remitido, cerrado…). Cada
paso trae su propia comprobación de integridad (hash del bloque + huella de la
nota pública).

Si la persona escribió "avísame" en el bot, cada cambio de estado le llega por
el mismo canal. Al cerrar el caso se borra su contacto.
"""
import asyncio
import logging

from app.core.config import settings
from app.services import firebase_db
from app.services.mensajeria import enviar_telegram, enviar_twilio, enviar_whatsapp_meta
from app.services.registro import ESTADOS_CASO, certificado_corto, hash_mensaje, verificar_bloque

log = logging.getLogger("escudo.seguimiento")

ICONOS = {"registrado": "📝", "en_revision": "🔎", "remitido": "📨", "en_investigacion": "🕵️", "cerrado": "✅"}


def evento_seguimiento(bloque: dict) -> dict:
    """Un paso de la línea de tiempo del caso, con su propia comprobación de integridad."""
    nota = bloque.get("nota", "")
    return {
        "certificado": bloque["hash"],
        "altura": bloque["altura"],
        "fecha": bloque["fecha"],
        "estado": bloque["estado"],
        "etiqueta": ESTADOS_CASO.get(bloque["estado"], bloque["estado"]),
        "actor": bloque.get("actor", ""),
        "nota": nota,
        "integro": verificar_bloque(bloque["hash"], bloque) and hash_mensaje(nota) == bloque.get("hash_nota"),
    }


def linea_de_tiempo(caso: dict) -> list[dict]:
    """El reporte (registrado) seguido de cada cambio de estado encadenado."""
    inicio = {"certificado": caso["hash"], "altura": caso["altura"], "fecha": caso["fecha"],
              "estado": "registrado", "etiqueta": ESTADOS_CASO["registrado"], "actor": "Escudo Comunitario",
              "nota": "", "integro": verificar_bloque(caso["hash"], caso)}
    return [inicio] + [evento_seguimiento(b) for b in firebase_db.seguimientos_de(caso["hash"])]


def _fecha(iso: str) -> str:
    return iso[:16].replace("T", " ") + " UTC"


def texto_linea_de_tiempo(caso: str, tiempo: list[dict]) -> str:
    """Línea de tiempo en formato de chat (WhatsApp/Telegram)."""
    lineas = [f"📋 *Tu caso {certificado_corto(caso)}…*", ""]
    for evento in tiempo:
        marca = "" if evento["integro"] else " ⚠️ alterado"
        lineas.append(f"{ICONOS.get(evento['estado'], '•')} *{evento['etiqueta']}*{marca}")
        lineas.append(f"   {_fecha(evento['fecha'])}" + (f" · {evento['actor']}" if evento["estado"] != "registrado" else ""))
        if evento["nota"]:
            lineas.append(f"   “{evento['nota']}”")
    if tiempo[-1]["estado"] != "cerrado":
        lineas += ["", "Cada avance queda encadenado y sellado: nadie puede cambiarlo después."]
    lineas.append(f"{settings.APP_URL}/verificar/{caso}")
    return "\n".join(lineas)


def texto_avance(caso: str, evento: dict) -> str:
    lineas = [f"🔔 *Novedad en tu caso {certificado_corto(caso)}…*",
              f"{ICONOS.get(evento['estado'], '•')} *{evento['etiqueta']}* · {evento['actor']}"]
    if evento["nota"]:
        lineas.append(f"“{evento['nota']}”")
    lineas.append(f"{settings.APP_URL}/verificar/{caso}")
    return "\n".join(lineas)


async def notificar_avance(caso: str, evento: dict) -> int:
    """Avisa a quien pidió seguimiento. Retorna cuántos avisos salieron. Nunca falla."""
    try:
        destinos = await asyncio.to_thread(firebase_db.avisos_caso, caso)
    except Exception as error:
        log.warning("No se pudieron leer los avisos del caso: %s", error)
        return 0
    texto = texto_avance(caso, evento)
    envios = []
    for d in destinos:
        if d.get("canal") == "telegram":
            envios.append(enviar_telegram(d["destino"], texto))
        elif d.get("canal") == "whatsapp_meta":
            envios.append(enviar_whatsapp_meta(d["destino"], texto))
        elif d.get("canal") == "whatsapp":
            envios.append(asyncio.to_thread(enviar_twilio, d["destino"], texto))
    resultados = await asyncio.gather(*envios, return_exceptions=True) if envios else []
    if evento["estado"] == "cerrado":
        try:
            await asyncio.to_thread(firebase_db.borrar_avisos_caso, caso)
        except Exception as error:
            log.warning("No se pudo borrar el contacto del caso cerrado: %s", error)
    return sum(1 for r in resultados if r is True)
