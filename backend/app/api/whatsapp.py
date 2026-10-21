"""
Webhook de Twilio para el canal de WhatsApp (conversacional y multimodal).

Twilio envía POST form-encoded (From, Body, NumMedia, MediaUrl0..N,
MediaContentType0..N, Latitude, Longitude) y espera TwiML. El canal:

  - Valida la firma X-Twilio-Signature (nadie más puede inyectar reportes).
  - Acepta texto, capturas, PDF y NOTAS DE VOZ (pensado para personas con
    baja alfabetización digital: pueden contar lo que pasó hablando).
  - Conversa en varios turnos: tras el veredicto pregunta la UPZ (número
    1-5) o la ubicación de WhatsApp 📍, y la agrega al reporte.
  - Comandos: "hola"/"ayuda" (menú), "verificar <certificado>".
"""
import base64
import logging
import re

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import settings
from app.services import firebase_db
from app.services.anonimizar import generalizar_ubicacion, seudonimo
from app.services.archivos import AdjuntoInvalidoError, preparar_adjuntos
from app.services.geolocalizacion import UPZ_BOSA, dentro_de_bosa, obtener_coordenadas
from app.services.procesamiento import procesar_reporte
from app.services.registro import certificado_corto, verificar_bloque

router = APIRouter()
log = logging.getLogger("escudo.whatsapp")

UPZ_MENU = list(UPZ_BOSA)  # orden estable: 1 Apogeo, 2 Bosa Occidental, ...
MENU_UPZ = "\n".join(f"*{i}* {nombre}" for i, nombre in enumerate(UPZ_MENU, 1))

SALUDO = (
    "🛡️ *Escudo Comunitario Bosa*\n"
    "¿Te llegó un mensaje raro? Te ayudo a saber si es fraude.\n\n"
    "Puedes:\n"
    "✍️ Reenviarme el mensaje\n"
    "📸 Mandarme una captura de pantalla\n"
    "🎤 Mandarme una *nota de voz* contándome qué pasó\n\n"
    "Es gratis y anónimo. Para comprobar un certificado escribe: *verificar* y el código."
)

_SALUDOS = {"hola", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
            "menu", "menú", "ayuda", "inicio", "empezar", "hi"}

_TIMEOUT_DESCARGA = httpx.Timeout(10.0, connect=5.0)


def _twiml(*mensajes: str) -> Response:
    respuesta = MessagingResponse()
    for m in mensajes:
        respuesta.message(m[:1590])  # límite de WhatsApp vía Twilio
    return Response(content=str(respuesta), media_type="application/xml")


def _url_publica(request: Request) -> str:
    if settings.TWILIO_WEBHOOK_URL:
        return settings.TWILIO_WEBHOOK_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}{request.url.path}"


def _validar_firma(request: Request, params: dict):
    if not (settings.TWILIO_AUTH_TOKEN and settings.TWILIO_VALIDAR_FIRMA):
        return
    firma = request.headers.get("x-twilio-signature", "")
    validador = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    if not validador.validate(_url_publica(request), params, firma):
        log.warning("Firma de Twilio inválida para %s", _url_publica(request))
        raise HTTPException(status_code=403, detail="Firma de Twilio inválida")


async def _descargar_media(params: dict) -> list[dict]:
    """Descarga los adjuntos de Twilio (requieren auth básica con SID/token)."""
    total = int(params.get("NumMedia") or 0)
    auth = (settings.TWILIO_ACCOUNT_SID or "", settings.TWILIO_AUTH_TOKEN or "")
    limite = max(settings.MAX_PESO_MB, settings.MAX_PESO_AUDIO_MB) * 1024 * 1024
    crudos = []
    async with httpx.AsyncClient(timeout=_TIMEOUT_DESCARGA, follow_redirects=True) as client:
        for i in range(min(total, settings.MAX_ARCHIVOS)):
            url = params.get(f"MediaUrl{i}")
            if not url:
                continue
            mime = params.get(f"MediaContentType{i}") or "application/octet-stream"
            try:
                resp = await client.get(url, auth=auth)
                resp.raise_for_status()
            except Exception as error:
                log.warning("No se pudo descargar un adjunto: %s", type(error).__name__)
                continue
            if len(resp.content) > limite:
                continue
            tipo_real = resp.headers.get("content-type", "").split(";")[0].strip()
            if tipo_real.startswith(("image/", "audio/", "application/pdf", "text/")):
                mime = tipo_real
            extension = mime.split("/")[-1]
            crudos.append({
                "nombre": f"{'nota_de_voz' if mime.startswith('audio/') else 'whatsapp_media'}_{i}.{extension}",
                "mime": mime,
                "base64": base64.b64encode(resp.content).decode("ascii"),
            })
    return crudos


def _formatear_veredicto(r: dict) -> str:
    nivel, riesgo, confianza = r["nivel"], r["nivel_riesgo"], r["confianza"]
    encabezado = {
        "alto": f"🚨 *MUY PROBABLE FRAUDE · riesgo {riesgo}%*",
        "medio": f"⚠️ *CUIDADO · riesgo {riesgo}%*",
        "bajo": f"✅ *Riesgo bajo · {riesgo}%*",
    }[nivel]
    lineas = [encabezado, f"Confianza del análisis: *{r['nivel_confianza']}* ({confianza}%)"]
    if nivel != "bajo":
        lineas.append(f"Tipo: {r['tipo_fraude']['nombre']}")
    if r.get("texto_detectado") and any(a["mime"].startswith("audio/") for a in r.get("adjuntos", [])):
        lineas.append(f"🎤 Entendí: “{r['texto_detectado'][:160]}”")
    lineas.append("")
    lineas.append(r["resumen"])

    externos = [h for h in r["verificacion"]["hallazgos"] if not h.get("simulada")][:2]
    if externos:
        lineas.append("")
        lineas.append("🔎 *Lo comprobamos:*")
        lineas += [f"• {h['detalle']}" for h in externos]

    lineas.append("")
    lineas.append("👉 *Qué hacer ahora:*")
    for i, paso in enumerate(r["plan_accion"][:3], 1):
        lineas.append(f"{i}. *{paso['titulo']}*. {paso['detalle']}")

    lineas.append("")
    lineas.append(f"🔒 Certificado: {certificado_corto(r['certificado'])}…")
    lineas.append(r["url_certificado"])
    return "\n".join(lineas)


def _responder_verificacion(texto: str) -> Response:
    codigo = re.sub(r"[^0-9a-f]", "", texto.lower().replace("verificar", ""))
    if len(codigo) < 16:
        return _twiml("Escribe *verificar* seguido del código del certificado (mínimo 16 caracteres).")
    try:
        bloque = firebase_db.buscar_bloque(codigo)
    except Exception:
        return _twiml("No pudimos consultar el registro en este momento. Intenta más tarde.")
    if not bloque:
        return _twiml("❌ No encontramos ese certificado en el registro.")
    integro = verificar_bloque(bloque["hash"], bloque)
    estado = "✅ *Íntegro*: el reporte no ha sido modificado." if integro else \
        "❌ *Alterado*: el contenido ya no coincide con su certificado."
    return _twiml(f"{estado}\nBloque #{bloque['altura']} · {bloque['fecha'][:16].replace('T', ' ')} UTC\n"
                  f"{settings.APP_URL}/verificar/{bloque['hash']}")


@router.post("/webhook")
async def recibir_whatsapp(request: Request):
    params = dict(await request.form())
    _validar_firma(request, params)

    remitente = params.get("From", "")
    usuario = seudonimo(remitente)
    texto = (params.get("Body") or "").strip()
    conversacion = {}
    try:
        conversacion = firebase_db.obtener_conversacion(usuario)
    except Exception as error:
        log.warning("Sin estado de conversación: %s", error)
    pendiente = conversacion.get("reporte_pendiente_upz")

    # 1. Ubicación compartida (📍) o número de UPZ para completar el último reporte
    lat_txt, lng_txt = params.get("Latitude"), params.get("Longitude")
    if pendiente and (lat_txt and lng_txt):
        lat, lng = float(lat_txt), float(lng_txt)
        if dentro_de_bosa(lat, lng):
            upz = min(UPZ_BOSA, key=lambda n: (UPZ_BOSA[n][0] - lat) ** 2 + (UPZ_BOSA[n][1] - lng) ** 2)
            firebase_db.actualizar_ubicacion(pendiente, upz, lat, lng, *generalizar_ubicacion(lat, lng))
            firebase_db.guardar_conversacion(usuario, {"reporte_pendiente_upz": None})
            return _twiml(f"📍 Gracias. Ubicamos tu reporte en la UPZ *{upz}*. "
                          f"Así alertamos a tus vecinos. ¡Cuídate!")
        return _twiml("Esa ubicación está fuera de Bosa. Responde con el número de tu UPZ:\n" + MENU_UPZ)

    if pendiente and re.fullmatch(r"[1-5]", texto) and int(params.get("NumMedia") or 0) == 0:
        upz = UPZ_MENU[int(texto) - 1]
        lat, lng = obtener_coordenadas(upz, seed=pendiente)
        firebase_db.actualizar_ubicacion(pendiente, upz, lat, lng, *generalizar_ubicacion(lat, lng))
        firebase_db.guardar_conversacion(usuario, {"reporte_pendiente_upz": None})
        return _twiml(f"✅ Listo, reporte ubicado en la UPZ *{upz}*. Gracias por proteger a tu comunidad. 🛡️")

    # 2. Comandos
    if texto.lower().startswith("verificar"):
        return _responder_verificacion(texto)

    tiene_media = int(params.get("NumMedia") or 0) > 0
    if not tiene_media and (texto.lower().strip("!¡.?¿ ") in _SALUDOS or len(texto) < 10):
        return _twiml(SALUDO)

    # 3. Reporte: descarga y validación de adjuntos
    adjuntos = []
    if tiene_media:
        crudos = await _descargar_media(params)
        validos = []
        for crudo in crudos:
            try:
                validos += preparar_adjuntos([crudo])
            except AdjuntoInvalidoError as error:
                log.info("Adjunto descartado: %s", error)
        adjuntos = validos
        if not adjuntos and not texto:
            return _twiml("No pude abrir ese archivo 😕. Envíame una captura (foto), un PDF o una nota de voz.")

    resultado = await procesar_reporte(
        mensaje=texto, adjuntos=adjuntos, canal="whatsapp", reportante=usuario,
        upz=None, lat=None, lng=None, rapido=True,
    )

    try:
        firebase_db.guardar_conversacion(usuario, {"reporte_pendiente_upz": resultado["certificado"]})
    except Exception as error:
        log.warning("No se pudo guardar la conversación: %s", error)

    pregunta = ("📍 *Ayúdanos a proteger a tus vecinos:* ¿en qué UPZ de Bosa estás? "
                "Responde con el número o comparte tu ubicación:\n" + MENU_UPZ)
    return _twiml(_formatear_veredicto(resultado), pregunta)
