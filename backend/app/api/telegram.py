"""
Canal de Telegram (gratuito): mismo bot conversacional que WhatsApp.

Telegram envía cada mensaje como JSON a POST /api/telegram/webhook con la
cabecera X-Telegram-Bot-Api-Secret-Token (se valida). El bot acepta texto,
fotos/capturas, PDF, notas de voz y la ubicación nativa (📍), y ofrece la UPZ
con botones. Comandos:

  /start      saludo y cómo usarlo
  /verificar  <código>  comprueba un certificado
  /alertas    el chat (de un líder comunitario) recibe las alertas tempranas por UPZ
  /cancelar   deja de recibir alertas

Configuración: TELEGRAM_BOT_TOKEN en Vercel y `python scripts/configurar_telegram.py`.
"""
import base64
import logging
import re

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.services import firebase_db
from app.services.anonimizar import seudonimo
from app.services.mensajeria import accion_telegram, descargar_telegram, enviar_telegram

from app.api.whatsapp import conversar

router = APIRouter()
log = logging.getLogger("escudo.telegram")

_MIME_AUDIO = "audio/ogg"  # las notas de voz de Telegram son OGG/Opus


async def _adjuntos(mensaje: dict) -> list[dict]:
    """Foto (mayor resolución), nota de voz, audio o documento → adjuntos crudos en Base64."""
    candidatos = []
    if mensaje.get("photo"):
        candidatos.append((mensaje["photo"][-1]["file_id"], "image/jpeg", "captura.jpg"))
    if mensaje.get("voice"):
        candidatos.append((mensaje["voice"]["file_id"], mensaje["voice"].get("mime_type", _MIME_AUDIO), "nota_de_voz.ogg"))
    if mensaje.get("audio"):
        candidatos.append((mensaje["audio"]["file_id"], mensaje["audio"].get("mime_type", "audio/mpeg"), "audio"))
    if mensaje.get("document"):
        doc = mensaje["document"]
        candidatos.append((doc["file_id"], doc.get("mime_type", "application/octet-stream"), doc.get("file_name", "archivo")))
    crudos = []
    for file_id, mime, nombre in candidatos[:settings.MAX_ARCHIVOS]:
        datos = await descargar_telegram(file_id)
        if datos:
            crudos.append({"nombre": nombre, "mime": mime, "base64": base64.b64encode(datos).decode("ascii")})
    return crudos


async def _comando(chat_id: int, texto: str, nombre: str) -> bool:
    """Atiende /alertas y /cancelar. Retorna True si el mensaje era uno de ellos."""
    comando = texto.split()[0].split("@")[0].lower() if texto.startswith("/") else ""
    if comando == "/alertas":
        firebase_db.suscribir_lider("telegram", str(chat_id), nombre)
        await enviar_telegram(chat_id, "🔔 *Listo.* Este chat recibirá las *alertas tempranas* cuando se detecte un "
                                       "brote de fraude en una UPZ de Bosa. Escribe /cancelar para dejar de recibirlas.")
        return True
    if comando == "/cancelar":
        firebase_db.desuscribir_lider("telegram", str(chat_id))
        await enviar_telegram(chat_id, "🔕 Ya no recibirás alertas tempranas en este chat.")
        return True
    return False


@router.post("/webhook")
async def recibir_telegram(request: Request, x_telegram_bot_api_secret_token: str = Header("")):
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram no está configurado (TELEGRAM_BOT_TOKEN).")
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Secreto del webhook inválido")

    update = await request.json()
    mensaje = update.get("message") or update.get("edited_message")
    if not mensaje or "chat" not in mensaje:
        return {"ok": True}  # otros tipos de actualización no se procesan

    chat_id = mensaje["chat"]["id"]
    texto = (mensaje.get("text") or mensaje.get("caption") or "").strip()
    nombre = mensaje.get("from", {}).get("first_name", "")

    try:
        if await _comando(chat_id, texto, nombre):
            return {"ok": True}

        # /start → saludo; /verificar CODIGO → comando del bot; "3. Bosa Central" (botón) → "3"
        if texto.lower().startswith("/start"):
            texto = "hola"
        elif texto.lower().startswith("/verificar"):
            texto = "verificar " + texto[len("/verificar"):]
        elif re.match(r"^[1-5]\.\s", texto):
            texto = texto[0]

        ubicacion = mensaje.get("location") or {}
        await accion_telegram(chat_id)
        crudos = await _adjuntos(mensaje)
        turno = await conversar(
            usuario=seudonimo(f"telegram:{chat_id}"), texto=texto, crudos=crudos,
            lat=ubicacion.get("latitude"), lng=ubicacion.get("longitude"),
            canal="telegram", sellar_en_linea=True,
        )
        mensajes = turno["mensajes"]
        for i, m in enumerate(mensajes):
            ultimo = i == len(mensajes) - 1
            await enviar_telegram(chat_id, m, opciones=turno.get("opciones") if ultimo else None,
                                  pedir_ubicacion=ultimo)
    except Exception as error:
        # Telegram reintenta si no recibe 200: se responde siempre para no duplicar reportes
        log.exception("Error atendiendo Telegram: %s", error)
        await enviar_telegram(chat_id, "😕 Tuvimos un problema analizando tu mensaje. Inténtalo de nuevo en un momento.")
    return {"ok": True}
