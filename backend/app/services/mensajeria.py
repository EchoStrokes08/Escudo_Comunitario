"""
Envío y descarga de medios en los canales gratuitos de mensajería:

  - Telegram Bot API (https://core.telegram.org/bots/api)
  - WhatsApp Cloud API de Meta (https://developers.facebook.com/docs/whatsapp/cloud-api)
  - WhatsApp vía Twilio (mensajes salientes: alertas y avances del caso)

Los textos del bot usan el formato de WhatsApp (*negrita*); para Telegram se
convierten a HTML.
"""
import html
import logging
import re

import httpx

from app.core.config import settings
from app.core.red import SSL

log = logging.getLogger("escudo.mensajeria")
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


# --------------------------------------------------------------------------- #
# Telegram
# --------------------------------------------------------------------------- #

def _url_telegram(metodo: str) -> str:
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{metodo}"


def whatsapp_a_html(texto: str) -> str:
    """*negrita* (formato WhatsApp) → <b>negrita</b>, escapando el resto para parse_mode=HTML."""
    seguro = html.escape(texto, quote=False)
    return re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", seguro)


async def enviar_telegram(chat_id: int | str, texto: str, opciones: list[str] | None = None,
                          pedir_ubicacion: bool = False) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    cuerpo: dict = {"chat_id": chat_id, "text": whatsapp_a_html(texto)[:4000], "parse_mode": "HTML",
                    "disable_web_page_preview": True}
    if opciones:
        botones = [[{"text": f"{i}. {nombre}"}] for i, nombre in enumerate(opciones, 1)]
        if pedir_ubicacion:
            botones.append([{"text": "📍 Compartir mi ubicación", "request_location": True}])
        cuerpo["reply_markup"] = {"keyboard": botones, "one_time_keyboard": True, "resize_keyboard": True}
    else:
        cuerpo["reply_markup"] = {"remove_keyboard": True}
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT) as client:
            resp = await client.post(_url_telegram("sendMessage"), json=cuerpo)
        if resp.status_code != 200:
            log.warning("Telegram sendMessage %s: %s", resp.status_code, resp.text[:200])
        return resp.status_code == 200
    except Exception as error:
        log.warning("Telegram sendMessage falló: %s", type(error).__name__)
        return False


async def enviar_audio_telegram(chat_id: int | str, audio: bytes, titulo: str = "Resultado del análisis") -> bool:
    """MP3 como audio reproducible (sendVoice exige OGG/Opus)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return False
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT) as client:
            resp = await client.post(_url_telegram("sendAudio"),
                                     data={"chat_id": str(chat_id), "title": titulo, "performer": "Escudo Comunitario"},
                                     files={"audio": ("escudo-resultado.mp3", audio, "audio/mpeg")})
        if resp.status_code != 200:
            log.warning("Telegram sendAudio %s: %s", resp.status_code, resp.text[:200])
        return resp.status_code == 200
    except Exception as error:
        log.warning("Telegram sendAudio falló: %s", type(error).__name__)
        return False


async def accion_telegram(chat_id: int | str, accion: str = "typing"):
    """Muestra "escribiendo…" mientras la IA analiza."""
    if settings.TELEGRAM_BOT_TOKEN:
        try:
            async with httpx.AsyncClient(verify=SSL, timeout=5) as client:
                await client.post(_url_telegram("sendChatAction"), json={"chat_id": chat_id, "action": accion})
        except Exception:
            pass


async def descargar_telegram(file_id: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT) as client:
            info = await client.get(_url_telegram("getFile"), params={"file_id": file_id})
            ruta = info.json()["result"]["file_path"]
            resp = await client.get(f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{ruta}")
            resp.raise_for_status()
            return resp.content
    except Exception as error:
        log.warning("No se pudo descargar el archivo de Telegram: %s", type(error).__name__)
        return None


# --------------------------------------------------------------------------- #
# WhatsApp Cloud API (Meta)
# --------------------------------------------------------------------------- #

def _url_graph(ruta: str) -> str:
    return f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{ruta}"


def _cabeceras_meta() -> dict:
    return {"Authorization": f"Bearer {settings.META_WHATSAPP_TOKEN}"}


def _destino_meta(numero: str) -> dict:
    # Teléfono → "to"; BSUID (usuario que oculta su número, ej. "CO.1736...") → "recipient"
    if re.fullmatch(r"[+\d\s-]+", numero):
        return {"to": re.sub(r"\D", "", numero)}
    return {"recipient": numero}


async def enviar_whatsapp_meta(numero: str, texto: str, opciones: list[str] | None = None) -> bool:
    if not (settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID):
        return False
    if not numero:
        return False
    destino = _destino_meta(numero)
    if opciones:
        # Mensaje de lista: la persona elige la UPZ con un toque
        cuerpo = {
            "messaging_product": "whatsapp", **destino, "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": texto[:1020]},
                "action": {"button": "Elegir UPZ", "sections": [{
                    "title": "UPZ de Bosa",
                    "rows": [{"id": str(i), "title": nombre[:24]} for i, nombre in enumerate(opciones, 1)],
                }]},
            },
        }
    else:
        cuerpo = {"messaging_product": "whatsapp", **destino, "type": "text",
                  "text": {"body": texto[:4000], "preview_url": False}}
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT) as client:
            resp = await client.post(_url_graph(f"{settings.META_PHONE_NUMBER_ID}/messages"),
                                     json=cuerpo, headers=_cabeceras_meta())
        if resp.status_code != 200:
            log.warning("Meta WhatsApp envío %s: %s", resp.status_code, resp.text[:300])
        return resp.status_code == 200
    except Exception as error:
        log.warning("Meta WhatsApp envío falló: %s", type(error).__name__)
        return False


async def enviar_audio_meta(numero: str, audio: bytes) -> bool:
    """Sube el MP3 a Meta y lo envía como mensaje de audio."""
    if not (settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID and numero):
        return False
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT) as client:
            subida = await client.post(_url_graph(f"{settings.META_PHONE_NUMBER_ID}/media"),
                                       data={"messaging_product": "whatsapp", "type": "audio/mpeg"},
                                       files={"file": ("escudo-resultado.mp3", audio, "audio/mpeg")},
                                       headers=_cabeceras_meta())
            subida.raise_for_status()
            cuerpo = {"messaging_product": "whatsapp", **_destino_meta(numero), "type": "audio",
                      "audio": {"id": subida.json()["id"]}}
            resp = await client.post(_url_graph(f"{settings.META_PHONE_NUMBER_ID}/messages"),
                                     json=cuerpo, headers=_cabeceras_meta())
        if resp.status_code != 200:
            log.warning("Meta WhatsApp audio %s: %s", resp.status_code, resp.text[:300])
        return resp.status_code == 200
    except Exception as error:
        log.warning("Meta WhatsApp audio falló: %s", type(error).__name__)
        return False


async def descargar_meta(media_id: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT, follow_redirects=True) as client:
            info = (await client.get(_url_graph(media_id), headers=_cabeceras_meta())).json()
            resp = await client.get(info["url"], headers=_cabeceras_meta())
            resp.raise_for_status()
            return resp.content, info.get("mime_type", "application/octet-stream")
    except Exception as error:
        log.warning("No se pudo descargar el medio de Meta: %s", type(error).__name__)
        return None


# --------------------------------------------------------------------------- #
# WhatsApp vía Twilio (salientes)
# --------------------------------------------------------------------------- #

def enviar_twilio(destino: str, texto: str) -> bool:
    """Mensaje saliente por Twilio (síncrono: llamarlo con asyncio.to_thread)."""
    if not (settings.TWILIO_WHATSAPP_FROM and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        return False
    from twilio.rest import Client

    destino = destino if destino.startswith("whatsapp:") else f"whatsapp:{destino}"
    try:
        Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN).messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM, to=destino, body=texto[:1590])
        return True
    except Exception as error:
        log.warning("No se pudo enviar por Twilio: %s", error)
        return False
