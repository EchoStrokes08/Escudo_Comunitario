"""
Webhook de Twilio para el canal de WhatsApp (multimodal).

Twilio envía los mensajes como POST form-encoded (From, Body, MediaUrl0..N,
MediaContentType0..N) y espera una respuesta TwiML en XML con
<MessagingResponse>. Los archivos adjuntos (capturas, facturas PDF) se
descargan con autenticación de Twilio, se validan y se envían al agente LLM.
"""
import base64

import httpx
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import settings
from app.services.analizador import evaluar_fraude
from app.services.archivos import AdjuntoInvalidoError, preparar_adjuntos, resumen_evidencia
from app.services.certificado import generar_certificado, certificado_corto
from app.services.firebase_db import guardar_alerta
from app.services.geolocalizacion import obtener_coordenadas
from app.services.verificador import verificar_mensaje, riesgo_verificado

router = APIRouter()

# Respuesta base si Twilio llega a enviar un cuerpo vacío
SALUDO = (
    "🛡️ *Escudo Comunitario Bosa*\n"
    "Envíanos el mensaje sospechoso que recibiste (también puedes adjuntar "
    "una captura o factura) y te diremos si es fraude."
)

MAX_PESO_BYTES = settings.MAX_PESO_MB * 1024 * 1024
_TIMEOUT_DESCARGA = httpx.Timeout(10.0, connect=5.0)


async def _descargar_media_twilio(media_urls: list[str],
                                  media_types: list[str]) -> list[dict]:
    """
    Descarga los adjuntos de Twilio (los MediaUrl exigen autenticación básica
    con SID/token) y los convierte al formato crudo [{nombre, mime, base64}].
    Un fallo en un archivo no detiene el análisis del mensaje.
    """
    adjuntos_crudos = []
    auth = (settings.TWILIO_ACCOUNT_SID or "", settings.TWILIO_AUTH_TOKEN or "")

    for indice, url in enumerate(media_urls[:settings.MAX_ARCHIVOS]):
        if not url:
            continue
        mime = (media_types[indice] if indice < len(media_types) else "") \
            or "application/octet-stream"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_DESCARGA,
                                         follow_redirects=True) as client:
                resp = await client.get(url, auth=auth)
                resp.raise_for_status()

            contenido = resp.content
            if len(contenido) > MAX_PESO_BYTES:
                continue  # adjunto demasiado pesado: se omite, el texto sigue

            # Confirma el Content-Type real si Twilio lo envía
            tipo_real = resp.headers.get("content-type", "").split(";")[0].strip()
            if tipo_real.startswith(("image/", "application/pdf", "text/")):
                mime = tipo_real

            adjuntos_crudos.append({
                "nombre": f"whatsapp_media_{indice}",
                "mime": mime,
                "base64": base64.b64encode(contenido).decode("ascii"),
            })
        except Exception:
            continue  # medio inaccesible: análisis de texto continúa

    return adjuntos_crudos


@router.post("/webhook")
async def recibir_whatsapp(
    From: str = Form(...),
    Body: str = Form(""),
    MediaUrl0: str = Form(None),
    MediaUrl1: str = Form(None),
    MediaUrl2: str = Form(None),
    MediaContentType0: str = Form(None),
    MediaContentType1: str = Form(None),
    MediaContentType2: str = Form(None),
):
    mensaje = (Body or "").strip()

    # 1. Captura y descarga de adjuntos (máx. MAX_ARCHIVOS)
    media_urls = [MediaUrl0, MediaUrl1, MediaUrl2]
    media_types = [MediaContentType0, MediaContentType1, MediaContentType2]
    adjuntos = []
    if any(media_urls):
        crudos = await _descargar_media_twilio(media_urls, media_types)
        try:
            adjuntos = preparar_adjuntos(crudos)
        except AdjuntoInvalidoError:
            adjuntos = []  # formato/peso inválido: se analiza solo el texto

    if not mensaje and not adjuntos:
        respuesta = MessagingResponse()
        respuesta.message(SALUDO)
        return Response(content=str(respuesta), media_type="application/xml")

    # 2. Detección avanzada con IA (agente multimodal: texto + archivos)
    analisis = await evaluar_fraude(mensaje, adjuntos)

    # 3. Verificación en fuentes abiertas (dominios maliciosos + reportes CAI Virtual)
    verificacion = verificar_mensaje(mensaje)
    nivel_riesgo = riesgo_verificado(verificacion, analisis["nivel_riesgo"])

    # 4. Certificado inmanipulable (SHA-256 del texto + huellas de adjuntos)
    evidencia = resumen_evidencia(adjuntos)
    certificado = generar_certificado(f"{mensaje}\n{evidencia}", nivel_riesgo)

    # 5. Guardar evidencia en Firebase (georreferenciado dentro de Bosa)
    lat, lng = obtener_coordenadas(None, seed=From)
    guardar_alerta(
        From,
        mensaje,
        nivel_riesgo,
        certificado,
        canal="whatsapp",
        flags=analisis["flags"],
        resumen=analisis["resumen"],
        verificacion=verificacion,
        lat=lat,
        lng=lng,
        motor=analisis.get("motor", ""),
        adjuntos=[{
            "nombre": a["nombre"],
            "mime": a["mime"],
            "tamano": a["tamano"],
            "sha256": a["sha256"],
        } for a in adjuntos],
    )

    # 6. Formatear la respuesta XML que Twilio entiende
    respuesta = MessagingResponse()
    corto = certificado_corto(certificado)
    nota_adjunto = f"\n📎 Archivos analizados: {len(adjuntos)}" if adjuntos else ""

    if verificacion["arriesgado"]:
        detalle = verificacion["hallazgos"][0]
        respuesta.message(
            f"🚨 *PELIGRO ALTO: {nivel_riesgo}%*\n"
            f"Tu mensaje coincide con reportes de fraude:\n"
            f"• {detalle['valor']} — {detalle['detalle']}\n"
            f"{nota_adjunto}\n\n"
            f"🔒 Certificado: {corto}…"
        )
    elif nivel_riesgo >= 50:
        flags_txt = "\n".join(f"• {f}" for f in analisis["flags"][:3])
        respuesta.message(
            f"⚠️ *Alerta de Riesgo: {nivel_riesgo}%*\n"
            f"Patrones de fraude detectados. No ingreses a los enlaces ni compartas datos.\n"
            f"{flags_txt}{nota_adjunto}\n\n"
            f"🛡️ Certificado de reporte: {corto}…"
        )
    else:
        respuesta.message(
            f"✅ *Riesgo bajo ({nivel_riesgo}%)*\n"
            f"{analisis['resumen']}{nota_adjunto}\n\n"
            f"🛡️ Certificado de reporte: {corto}…"
        )

    return Response(content=str(respuesta), media_type="application/xml")
