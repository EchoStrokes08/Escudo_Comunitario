"""
WhatsApp oficial de Meta (Cloud API): alternativa gratuita a Twilio.

  GET  /api/whatsapp-meta/webhook   verificación del webhook (hub.challenge)
  POST /api/whatsapp-meta/webhook   mensajes entrantes (texto, imagen, audio, documento,
                                    ubicación y respuesta de la lista de UPZ)

Meta ofrece un número de prueba gratuito que puede escribir hasta a 5 números
verificados. Variables: META_WHATSAPP_TOKEN, META_PHONE_NUMBER_ID y, opcionales,
META_VERIFY_TOKEN y META_APP_SECRET (valida la firma X-Hub-Signature-256).
"""
import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.core.config import settings
from app.services import firebase_db
from app.services.anonimizar import seudonimo
from app.services.mensajeria import descargar_meta, enviar_whatsapp_meta

from app.api.whatsapp import conversar

router = APIRouter()
log = logging.getLogger("escudo.whatsapp_meta")

_TIPOS_MEDIA = {"image", "audio", "document", "sticker"}


@router.get("/webhook")
def verificar_webhook(hub_mode: str = Query("", alias="hub.mode"),
                      hub_verify_token: str = Query("", alias="hub.verify_token"),
                      hub_challenge: str = Query("", alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token de verificación inválido")


def _validar_firma(cuerpo: bytes, firma: str):
    if not settings.META_APP_SECRET:
        return
    esperada = "sha256=" + hmac.new(settings.META_APP_SECRET.encode(), cuerpo, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(esperada, firma or ""):
        raise HTTPException(status_code=403, detail="Firma de Meta inválida")


def _remitente(mensaje: dict) -> str:
    """Teléfono del remitente o, si usa nombre de usuario y oculta su número, su BSUID (from_user_id)."""
    return mensaje.get("from") or mensaje.get("from_user_id") or ""


async def _atender(mensaje: dict):
    numero = _remitente(mensaje)
    tipo = mensaje.get("type")
    texto, lat, lng, crudos = "", None, None, []

    if tipo == "text":
        texto = mensaje["text"].get("body", "")
    elif tipo == "interactive":
        respuesta = mensaje["interactive"].get("list_reply") or mensaje["interactive"].get("button_reply") or {}
        texto = respuesta.get("id", "")  # la lista de UPZ usa como id el número 1-5
    elif tipo == "location":
        lat, lng = mensaje["location"].get("latitude"), mensaje["location"].get("longitude")
    elif tipo in _TIPOS_MEDIA:
        media = mensaje[tipo]
        texto = media.get("caption", "")
        descarga = await descargar_meta(media["id"])
        if descarga:
            datos, mime = descarga
            nombre = media.get("filename") or ("nota_de_voz" if tipo == "audio" else tipo)
            crudos.append({"nombre": nombre, "mime": mime, "base64": base64.b64encode(datos).decode("ascii")})

    if texto.strip().lower() in ("alertas", "/alertas"):
        firebase_db.suscribir_lider("whatsapp_meta", numero)
        await enviar_whatsapp_meta(numero, "🔔 Listo. Recibirás las *alertas tempranas* de fraude en Bosa. "
                                           "Escribe *cancelar alertas* para dejar de recibirlas.")
        return
    if texto.strip().lower() in ("cancelar alertas", "/cancelar"):
        firebase_db.desuscribir_lider("whatsapp_meta", numero)
        await enviar_whatsapp_meta(numero, "🔕 Ya no recibirás alertas tempranas.")
        return

    turno = await conversar(
        usuario=seudonimo(f"whatsapp:+{numero}" if numero.isdigit() else f"whatsapp:{numero}"), texto=texto, crudos=crudos, lat=lat, lng=lng,
        canal="whatsapp", sellar_en_linea=True,
    )
    mensajes = turno["mensajes"]
    for i, m in enumerate(mensajes):
        ultimo = i == len(mensajes) - 1
        await enviar_whatsapp_meta(numero, m, opciones=turno.get("opciones") if ultimo else None)


@router.post("/webhook")
async def recibir_whatsapp_meta(request: Request):
    cuerpo = await request.body()
    _validar_firma(cuerpo, request.headers.get("x-hub-signature-256", ""))
    if not (settings.META_WHATSAPP_TOKEN and settings.META_PHONE_NUMBER_ID):
        raise HTTPException(status_code=503, detail="WhatsApp de Meta no está configurado.")

    datos = await request.json()
    for entrada in datos.get("entry", []):
        for cambio in entrada.get("changes", []):
            for mensaje in cambio.get("value", {}).get("messages", []):
                try:
                    await _atender(mensaje)
                except Exception as error:
                    # Meta reintenta si no recibe 200: se responde siempre para no duplicar reportes
                    log.exception("Error atendiendo WhatsApp de Meta: %s", error)
                    await enviar_whatsapp_meta(_remitente(mensaje), "😕 Tuvimos un problema analizando tu "
                                                                        "mensaje. Inténtalo de nuevo en un momento.")
    return {"ok": True}
