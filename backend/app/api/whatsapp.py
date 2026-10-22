"""
Webhook de Twilio para el canal de WhatsApp (conversacional y multimodal).

Twilio envía POST form-encoded (From, Body, NumMedia, MediaUrl0..N,
MediaContentType0..N, Latitude, Longitude) y espera TwiML. El canal:

  - Valida la firma X-Twilio-Signature (nadie más puede inyectar reportes).
  - Acepta texto, capturas, PDF y NOTAS DE VOZ (pensado para personas con
    baja alfabetización digital: pueden contar lo que pasó hablando).
  - Conversa en varios turnos: tras el veredicto pregunta la UPZ (número
    1-5) o la ubicación de WhatsApp 📍, y la agrega al reporte.
  - Comandos: "hola"/"ayuda" (menú), "verificar <certificado>",
    "estado [certificado]" (línea de tiempo del caso), "escuchar" (veredicto
    en audio) y "avísame" (recibir aquí los avances del caso).
  - Si la persona mandó una nota de voz, el veredicto también se le devuelve hablado.

POST /api/whatsapp/simulador expone el mismo bot al chat de la web (/chat),
para demos y para quien no tenga WhatsApp a mano.
"""
import base64
import logging
import re
import unicodedata

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import settings
from app.core.limite import limitar_por_ip
from app.core.red import SSL
from app.core.riesgo import nivel as nivel_riesgo
from app.services import firebase_db
from app.services.anonimizar import generalizar_ubicacion, seudonimo
from app.services.archivos import AdjuntoInvalidoError, preparar_adjuntos
from app.services.geolocalizacion import UPZ_BOSA, dentro_de_bosa, obtener_coordenadas
from app.services.procesamiento import procesar_reporte, revisar_brote, sellar
from app.services.registro import certificado_corto, es_seguimiento, verificar_bloque
from app.services.seguimiento import linea_de_tiempo, texto_linea_de_tiempo

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
    "Es gratis y anónimo. Después puedes escribir:\n"
    "🔊 *escuchar* para oír el resultado\n"
    "📋 *estado* para ver cómo va tu caso\n"
    "🔒 *verificar* y el código para comprobar un certificado"
)

_SALUDOS = {"hola", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches",
            "menu", "menú", "ayuda", "inicio", "empezar", "hi"}
# Palabras de saludo y cortesía: un mensaje hecho solo de ellas no es un reporte
_PALABRAS_SALUDO = {
    "hola", "holi", "hi", "hello", "ola", "buenas", "buenos", "buen", "dia", "dias", "tarde", "tardes",
    "noche", "noches", "que", "tal", "como", "estas", "esta", "estan", "va", "vas", "todo", "bien", "muy",
    "y", "tu", "usted", "ustedes", "menu", "ayuda", "inicio", "empezar", "start", "info", "informacion",
    "gracias", "ok", "oki", "listo", "vale", "si", "no", "bot", "escudo", "comunitario", "bosa", "amigo",
    "amiga", "hey", "saludos", "prueba", "probando", "test", "alguien", "ahi", "hay", "me", "ayudas",
    "puedes", "ayudar", "necesito", "quiero", "por", "favor", "porfa", "pf", "a", "el", "la", "de", "en",
}


def _es_saludo(texto: str) -> bool:
    """'Hola, buenas noches 👋', 'holaaa cómo estás?', 'probando'… → saludo; un mensaje real no."""
    if len(texto) < 10:
        return True
    plano = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    if re.search(r"\d|https?://|www\.|\.(com|co|net)\b", plano):
        return False
    palabras = re.findall(r"[a-z]+", plano)
    if not palabras:
        return True  # solo emojis o signos
    if len(palabras) > 12:
        return False
    # "holaaa" → "hola", "buenaaas" → "buenas"
    return all(p in _PALABRAS_SALUDO or re.sub(r"(.)\1+", r"\1", p) in _PALABRAS_SALUDO for p in palabras)

_TIMEOUT_DESCARGA = httpx.Timeout(10.0, connect=5.0)


def _twiml(*mensajes: str, audio_url: str | None = None) -> Response:
    respuesta = MessagingResponse()
    for m in mensajes:
        respuesta.message(m[:1590])  # límite de WhatsApp vía Twilio
    if audio_url:
        # Twilio descarga el MP3 de nuestra API y lo entrega como audio
        respuesta.message("🔊 Resultado en audio").media(audio_url)
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
    async with httpx.AsyncClient(verify=SSL, timeout=_TIMEOUT_DESCARGA, follow_redirects=True) as client:
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


# Twilio corta en 1.590 caracteres: el veredicto se arma por bloques y, si no cabe, se quitan
# primero los opcionales para que el certificado (al final) nunca se pierda
_LIMITE_MENSAJE = 1500


def _formatear_veredicto(r: dict) -> str:
    nivel, riesgo, confianza = r["nivel"], r["nivel_riesgo"], r["confianza"]
    encabezado = {
        "alto": f"🚨 *MUY PROBABLE FRAUDE · riesgo {riesgo}%*",
        "medio": f"⚠️ *CUIDADO · riesgo {riesgo}%*",
        "bajo": f"✅ *Riesgo bajo · {riesgo}%*",
    }[nivel]
    cabeza = [encabezado, f"Confianza del análisis: *{r['nivel_confianza']}* ({confianza}%)"]
    if nivel != "bajo":
        cabeza.append(f"Tipo de amenaza: *{r['tipo_fraude']['nombre']}*")
    if r.get("texto_detectado") and any(a["mime"].startswith("audio/") for a in r.get("adjuntos", [])):
        cabeza.append(f"🎤 Entendí: “{r['texto_detectado'][:160]}”")
    cabeza += ["", r["resumen"]]

    causas = r.get("causas", [])[:3]
    por_que = ["🔎 *Por qué:*"] + [  # ✔️ = confirmado por una fuente externa; • = lo que explica el análisis
        f"{'✔️' if c['origen'] == 'verificado' else '•'} {c['texto']}" for c in causas] if causas else []
    como = [f"💡 *Cómo funciona este engaño:* {r['tipo_fraude']['como_funciona']}"] if (
        nivel != "bajo" and r["tipo_fraude"].get("como_funciona")) else []
    pasos = r["plan_accion"][:3]
    plan = ["👉 *Qué hacer ahora:*"] + [f"{i}. *{p['titulo']}*. {p['detalle']}" for i, p in enumerate(pasos, 1)]
    plan_corto = ["👉 *Qué hacer ahora:*"] + [f"{i}. *{p['titulo']}*." for i, p in enumerate(pasos, 1)]
    cierre = [f"🔒 Certificado: {certificado_corto(r['certificado'])}…", r["url_certificado"]]

    def unir(*bloques: list[str]) -> str:
        return "\n\n".join("\n".join(b) for b in bloques if b)

    # De la versión más completa a la más corta; siempre conservan el porqué, el plan y el certificado
    for bloques in ((cabeza, por_que, como, plan, cierre), (cabeza, por_que, plan, cierre),
                    (cabeza, por_que, como, plan_corto, cierre), (cabeza, por_que, plan_corto, cierre)):
        texto = unir(*bloques)
        if len(texto) <= _LIMITE_MENSAJE:
            return texto
    return unir(cabeza, por_que[:3], plan_corto, cierre)


def _responder_verificacion(texto: str) -> list[str]:
    codigo = re.sub(r"[^0-9a-f]", "", texto.lower().replace("verificar", ""))
    if len(codigo) < 16:
        return ["Escribe *verificar* seguido del código del certificado (mínimo 16 caracteres)."]
    try:
        bloque = firebase_db.buscar_bloque(codigo)
    except Exception:
        return ["No pudimos consultar el registro en este momento. Intenta más tarde."]
    if not bloque:
        return ["❌ No encontramos ese certificado en el registro."]
    integro = verificar_bloque(bloque["hash"], bloque)
    estado = "✅ *Íntegro*: el reporte no ha sido modificado." if integro else \
        "❌ *Alterado*: el contenido ya no coincide con su certificado."
    return [f"{estado}\nBloque #{bloque['altura']} · {bloque['fecha'][:16].replace('T', ' ')} UTC\n"
            f"{settings.APP_URL}/verificar/{bloque['hash']}"]


def _responder_estado(texto: str, ultimo: str | None) -> list[str]:
    hallado = re.search(r"\b[0-9a-f]{16,64}\b", texto.lower())
    codigo = hallado.group(0) if hallado else ultimo
    if not codigo:
        return ["Escribe *estado* seguido del código de tu certificado (mínimo 16 caracteres)."]
    try:
        bloque = firebase_db.buscar_bloque(codigo)
        if bloque and es_seguimiento(bloque):
            bloque = firebase_db.obtener_bloque(bloque["caso"])
        if not bloque:
            return ["❌ No encontramos ese certificado en el registro."]
        return [texto_linea_de_tiempo(bloque["hash"], linea_de_tiempo(bloque))]
    except Exception as error:
        log.warning("No se pudo consultar el estado del caso: %s", error)
        return ["No pudimos consultar el registro en este momento. Intenta más tarde."]


def _plano(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode().strip("!¡.?¿/ ")


_PIDE_AVISOS = {"avisame", "avisenme", "avisar", "seguimiento"}
_PIDE_AUDIO = {"escuchar", "audio", "oir", "escuchar resultado"}


async def _ubicar(usuario: str, certificado: str, upz: str, lat: float, lng: float):
    """
    Completa la UPZ del reporte pendiente y revisa el brote en esa UPZ: en los chats el
    reporte se registra sin UPZ, así que la alerta temprana solo puede salir aquí.
    """
    firebase_db.actualizar_ubicacion(certificado, upz, lat, lng, *generalizar_ubicacion(lat, lng))
    firebase_db.guardar_conversacion(usuario, {"reporte_pendiente_upz": None})
    try:
        firebase_db.ubicar_indicadores(certificado, upz)
    except Exception as error:
        log.warning("No se pudo ubicar los indicadores: %s", error)
    try:
        publico = firebase_db.obtener_publico(certificado) or {}
    except Exception as error:
        log.warning("No se pudo leer el reporte ubicado: %s", error)
        return
    await revisar_brote(upz, publico.get("tipo_fraude", ""), nivel_riesgo(publico.get("nivel_riesgo", 0)))


async def conversar(*, usuario: str, texto: str, crudos: list[dict], lat: float | None, lng: float | None,
                    canal: str, sellar_en_linea: bool = False, destino: tuple[str, str] | None = None) -> dict:
    """
    Un turno de la conversación, compartido por todos los canales.
    destino: (canal, id) para avisar los avances del caso si la persona escribe "avísame"
    (None en el chat web, que consulta el estado en la página).
    Retorna {"mensajes": [...], "opciones": [...], "certificado": str | None,
             "voz": certificado cuyo veredicto conviene enviar también en audio | None}.
    """
    texto = (texto or "").strip()
    conversacion = {}
    try:
        conversacion = firebase_db.obtener_conversacion(usuario)
    except Exception as error:
        log.warning("Sin estado de conversación: %s", error)
    pendiente = conversacion.get("reporte_pendiente_upz")
    ultimo = conversacion.get("ultimo_certificado") or pendiente

    # 1. Ubicación compartida (📍) o número de UPZ para completar el último reporte
    if pendiente and lat is not None and lng is not None:
        if dentro_de_bosa(lat, lng):
            upz = min(UPZ_BOSA, key=lambda n: (UPZ_BOSA[n][0] - lat) ** 2 + (UPZ_BOSA[n][1] - lng) ** 2)
            await _ubicar(usuario, pendiente, upz, lat, lng)
            return {"mensajes": [f"📍 Gracias. Ubicamos tu reporte en la UPZ *{upz}*. "
                                 f"Así alertamos a tus vecinos. ¡Cuídate!"]}
        return {"mensajes": ["Esa ubicación está fuera de Bosa. Responde con el número de tu UPZ:\n" + MENU_UPZ],
                "opciones": UPZ_MENU}

    if pendiente and re.fullmatch(r"[1-5]", texto) and not crudos:
        upz = UPZ_MENU[int(texto) - 1]
        lat_upz, lng_upz = obtener_coordenadas(upz, seed=pendiente)
        await _ubicar(usuario, pendiente, upz, lat_upz, lng_upz)
        return {"mensajes": [f"✅ Listo, reporte ubicado en la UPZ *{upz}*. Gracias por proteger a tu comunidad. 🛡️"]}

    # 2. Comandos
    comando = _plano(texto)
    if comando.startswith("verificar"):
        return {"mensajes": _responder_verificacion(texto)}
    # Solo "estado" o "estado <código>": "Estado de su cuenta: bloqueada…" es un reporte, no un comando
    if re.fullmatch(r"estado(\s+(de\s+)?(mi\s+)?caso)?\s*[0-9a-f]*", comando):
        return {"mensajes": _responder_estado(texto, ultimo)}
    if comando in _PIDE_AUDIO and not crudos:
        if not ultimo:
            return {"mensajes": ["Aún no tienes un reporte. Envíame el mensaje sospechoso y te digo si es fraude."]}
        return {"mensajes": ["🔊 Aquí tienes el resultado en audio:"], "voz": ultimo}
    if comando in _PIDE_AVISOS and not crudos:
        if not ultimo:
            return {"mensajes": ["Primero envíame el mensaje sospechoso; después podrás pedir los avances de tu caso."]}
        if not destino:
            return {"mensajes": [f"Consulta los avances de tu caso aquí:\n{settings.APP_URL}/verificar/{ultimo}"]}
        try:
            firebase_db.suscribir_avisos_caso(ultimo, *destino)
        except Exception as error:
            log.warning("No se pudo guardar el aviso del caso: %s", error)
            return {"mensajes": ["No pudimos activar los avisos en este momento. Intenta más tarde."]}
        return {"mensajes": [f"🔔 Listo. Te escribiré aquí cada vez que tu caso {certificado_corto(ultimo)}… avance "
                             f"(revisión, remisión a la Policía o Fiscalía, cierre). Solo para eso guardamos este "
                             f"contacto, y lo borramos al cerrar el caso."]}

    if not crudos and (texto.lower().strip("!¡.?¿ ") in _SALUDOS or _es_saludo(texto)):
        return {"mensajes": [SALUDO]}

    # 3. Reporte: validación de adjuntos
    adjuntos = []
    for crudo in crudos[:settings.MAX_ARCHIVOS]:
        try:
            adjuntos += preparar_adjuntos([crudo])
        except AdjuntoInvalidoError as error:
            log.info("Adjunto descartado: %s", error)
    if crudos and not adjuntos and not texto:
        return {"mensajes": ["No pude abrir ese archivo 😕. Envíame una captura (foto), un PDF o una nota de voz."]}

    resultado = await procesar_reporte(
        mensaje=texto, adjuntos=adjuntos, canal=canal, reportante=usuario,
        upz=None, lat=None, lng=None, rapido=True,
    )
    if sellar_en_linea:
        # En WhatsApp nadie abre la página que pide el sello: se sella aquí (hay margen en los 15 s)
        await sellar(resultado["certificado"], timeout=2.5)

    try:
        firebase_db.guardar_conversacion(usuario, {"reporte_pendiente_upz": resultado["certificado"],
                                                   "ultimo_certificado": resultado["certificado"]})
    except Exception as error:
        log.warning("No se pudo guardar la conversación: %s", error)

    pregunta = ("📍 *Ayúdanos a proteger a tus vecinos:* ¿en qué UPZ de Bosa estás? "
                "Responde con el número o comparte tu ubicación:\n" + MENU_UPZ)
    if resultado["nivel"] != "bajo":
        pregunta += ("\n\n📋 Escribe *avísame* para recibir aquí los avances de tu caso o *estado* para consultarlo."
                     if destino else "\n\n📋 Escribe *estado* para ver cómo avanza tu caso.")
    # Quien habló probablemente prefiere escuchar: el veredicto también va en audio
    hablo = any(a["mime"].startswith("audio/") for a in adjuntos)
    return {"mensajes": [_formatear_veredicto(resultado), pregunta], "opciones": UPZ_MENU,
            "certificado": resultado["certificado"], "voz": resultado["certificado"] if hablo else None}


@router.post("/webhook")
async def recibir_whatsapp(request: Request):
    params = dict(await request.form())
    _validar_firma(request, params)

    crudos = await _descargar_media(params) if int(params.get("NumMedia") or 0) > 0 else []
    lat_txt, lng_txt = params.get("Latitude"), params.get("Longitude")
    turno = await conversar(
        usuario=seudonimo(params.get("From", "")), texto=params.get("Body") or "", crudos=crudos,
        lat=float(lat_txt) if lat_txt else None, lng=float(lng_txt) if lng_txt else None,
        canal="whatsapp", sellar_en_linea=True, destino=("whatsapp", params.get("From", "")),
    )
    audio = f"{settings.APP_URL}/api/voz/{turno['voz']}.mp3" if turno.get("voz") and settings.VOZ_RESPUESTAS else None
    return _twiml(*turno["mensajes"], audio_url=audio)


# --------------------------------------------------------------------------- #
# Simulador web (mismo bot, sin Twilio): respaldo para demos y pruebas
# --------------------------------------------------------------------------- #

class AdjuntoChat(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    mime: str = Field(..., min_length=3, max_length=100)
    base64: str = Field(..., min_length=1)


class MensajeChat(BaseModel):
    sesion: str = Field(..., min_length=8, max_length=64, description="Identificador aleatorio del navegador")
    texto: str = Field("", max_length=5000)
    adjuntos: list[AdjuntoChat] = Field(default_factory=list, max_length=settings.MAX_ARCHIVOS)
    lat: float | None = None
    lng: float | None = None


@router.post("/simulador")
async def simulador(mensaje: MensajeChat, request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    limitar_por_ip(ip or "desconocida")
    turno = await conversar(
        usuario=seudonimo(f"chat:{mensaje.sesion}"), texto=mensaje.texto,
        crudos=[a.model_dump() for a in mensaje.adjuntos], lat=mensaje.lat, lng=mensaje.lng,
        canal="chat",
    )
    # El navegador reproduce el audio desde la API (ruta relativa: mismo dominio en Vercel)
    turno["audio"] = f"/api/voz/{turno['voz']}.mp3" if turno.get("voz") and settings.VOZ_RESPUESTAS else None
    return turno
