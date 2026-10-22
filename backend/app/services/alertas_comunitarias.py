"""
Alerta temprana comunitaria.

Si en una UPZ se acumulan BROTE_MINIMO reportes de riesgo medio/alto del mismo
tipo de fraude en BROTE_VENTANA_HORAS, se publica una alerta en el panel
(colección alertas_comunitarias) y se avisa a los líderes comunitarios:

  - suscritos por Telegram (/alertas) o por WhatsApp de Meta ("alertas"): gratis
  - LIDERES_WHATSAPP vía Twilio, si está configurado

Cada combinación UPZ + tipo alerta como máximo una vez al día.
"""
import asyncio
import logging
import re

from app.core.config import settings
from app.services import firebase_db
from app.services.mensajeria import enviar_telegram, enviar_twilio, enviar_whatsapp_meta
from app.services.orientacion import nombre_tipo

log = logging.getLogger("escudo.alertas")


def _clave(upz: str, tipo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{upz}-{tipo}".lower()).strip("-")


def _avisar_twilio(texto: str) -> int:
    return sum(enviar_twilio(destino, texto) for destino in settings.LIDERES_WHATSAPP)


async def avisar_lideres(texto: str) -> int:
    """Envía la alerta por todos los canales disponibles. Retorna cuántos avisos salieron."""
    try:
        suscritos = await asyncio.to_thread(firebase_db.lideres_suscritos)
    except Exception as error:
        log.warning("No se pudieron leer los líderes suscritos: %s", error)
        suscritos = []
    envios = []
    for lider in suscritos:
        if lider.get("canal") == "telegram":
            envios.append(enviar_telegram(lider["destino"], texto))
        elif lider.get("canal") == "whatsapp_meta":
            envios.append(enviar_whatsapp_meta(lider["destino"], texto))
    resultados = await asyncio.gather(*envios) if envios else []
    return sum(1 for ok in resultados if ok) + await asyncio.to_thread(_avisar_twilio, texto)


def detectar_brote(upz: str, tipo: str) -> dict | None:
    """Retorna la alerta (aún sin enviar ni guardar) si hay un brote nuevo en la UPZ."""
    if tipo == "legitimo":
        return None
    clave = _clave(upz, tipo)
    if firebase_db.alerta_comunitaria_reciente(clave):
        return None
    recientes = [r for r in firebase_db.reportes_publicos_desde(settings.BROTE_VENTANA_HORAS)
                 if r.get("upz") == upz and r.get("tipo_fraude") == tipo and r.get("nivel_riesgo", 0) >= 40]
    if len(recientes) < settings.BROTE_MINIMO:
        return None
    nombre = nombre_tipo(tipo)
    return {
        "clave": clave,
        "upz": upz,
        "tipo_fraude": tipo,
        "nombre_tipo": nombre,
        "casos": len(recientes),
        "ventana_horas": settings.BROTE_VENTANA_HORAS,
        "mensaje": f"{len(recientes)} casos de {nombre.lower()} en {settings.BROTE_VENTANA_HORAS} h",
    }


async def emitir_alerta(alerta: dict) -> dict:
    texto = (f"🚨 *Alerta temprana · Escudo Comunitario*\n"
             f"En la UPZ *{alerta['upz']}* se reportaron {alerta['casos']} casos de "
             f"{alerta['nombre_tipo'].lower()} en las últimas {alerta['ventana_horas']} horas.\n"
             f"Avisa a tus vecinos: no compartan códigos ni consignen a cuentas desconocidas.\n"
             f"Panel: {settings.APP_URL}")
    alerta = {**alerta, "lideres_notificados": await avisar_lideres(texto)}
    clave = alerta.pop("clave")
    await asyncio.to_thread(firebase_db.guardar_alerta_comunitaria, clave, alerta)
    return alerta
