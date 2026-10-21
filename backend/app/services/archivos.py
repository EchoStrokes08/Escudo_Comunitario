"""
Soporte de archivos adjuntos (multimodal).

Valida los adjuntos que llegan del frontend o de Twilio (WhatsApp) y los
normaliza para que el agente LLM pueda procesarlos:
  - imágenes (PNG, JPEG, WEBP) → parte visual en Base64
  - PDF                        → parte PDF inline (Gemini) o texto extraído (OpenAI)
  - TXT                        → texto plano inyectado al prompt
  - audio (OGG, MP3, WAV)      → nota de voz: Gemini la transcribe y la analiza

Límites y formatos controlados por variables de entorno (MAX_PESO_MB,
MAX_PESO_AUDIO_MB, MAX_ARCHIVOS).
"""
import base64
import binascii
import hashlib
from io import BytesIO

from app.core.config import settings

MIME_SOPORTADOS = {
    "image/png", "image/jpeg", "image/webp", "application/pdf", "text/plain",
    "audio/ogg", "audio/mpeg", "audio/wav",
}

# Alias frecuentes (navegadores, Twilio) → MIME canónico
_ALIAS_MIME = {
    "image/jpg": "image/jpeg",
    "audio/x-wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/opus": "audio/ogg",
    "audio/mp3": "audio/mpeg",
}

# Firmas binarias (magic bytes) para validar que el archivo es lo que dice ser
_MAGIC_BYTES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/webp": (b"RIFF",),
    "application/pdf": (b"%PDF-",),
    "text/plain": (),  # texto plano sin firma binaria
    "audio/ogg": (b"OggS",),
    "audio/mpeg": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"),
    "audio/wav": (b"RIFF",),
}

# Segunda firma en el byte 8 para contenedores RIFF
_RIFF_SUBTIPO = {"image/webp": b"WEBP", "audio/wav": b"WAVE"}

MAX_PESO_BYTES = settings.MAX_PESO_MB * 1024 * 1024
MAX_PESO_AUDIO_BYTES = settings.MAX_PESO_AUDIO_MB * 1024 * 1024


def es_audio(mime: str) -> bool:
    return _normalizar_mime(mime).startswith("audio/")


class AdjuntoInvalidoError(Exception):
    """Error de validación de adjunto.

    codigo: "formato" | "peso" | "corrupto"
    """

    def __init__(self, mensaje: str, codigo: str = "formato"):
        super().__init__(mensaje)
        self.codigo = codigo


def _normalizar_mime(mime: str) -> str:
    mime = (mime or "").lower().split(";")[0].strip()
    return _ALIAS_MIME.get(mime, mime)


def validar_adjunto(nombre: str, mime: str, base64_data: str) -> bytes:
    """Valida tipo, firma binaria y peso; retorna los bytes crudos del archivo."""
    mime = _normalizar_mime(mime)

    if mime not in MIME_SOPORTADOS:
        soportados = ", ".join(sorted(MIME_SOPORTADOS))
        raise AdjuntoInvalidoError(
            f"'{nombre}': formato no soportado ({mime or 'desconocido'}). "
            f"Formatos válidos: {soportados}.",
            codigo="formato",
        )

    try:
        datos = base64.b64decode(base64_data, validate=True)
    except (binascii.Error, ValueError):
        raise AdjuntoInvalidoError(
            f"'{nombre}': el contenido del archivo está corrupto o no es Base64 válido.",
            codigo="corrupto",
        )

    if not datos:
        raise AdjuntoInvalidoError(f"'{nombre}': el archivo está vacío.", codigo="corrupto")

    limite_mb = settings.MAX_PESO_AUDIO_MB if es_audio(mime) else settings.MAX_PESO_MB
    if len(datos) > limite_mb * 1024 * 1024:
        raise AdjuntoInvalidoError(
            f"'{nombre}': el archivo pesa {len(datos) / 1_048_576:.1f} MB y el máximo es "
            f"{limite_mb} MB. Comprime el archivo o adjunta uno más pequeño.",
            codigo="peso",
        )

    firmas = _MAGIC_BYTES.get(mime, ())
    subtipo = _RIFF_SUBTIPO.get(mime)
    firma_invalida = firmas and not any(datos.startswith(f) for f in firmas)
    if firma_invalida or (subtipo and datos[8:12] != subtipo):
        raise AdjuntoInvalidoError(
            f"'{nombre}': el contenido no corresponde al tipo declarado ({mime}).",
            codigo="formato",
        )

    return datos


def extraer_texto_txt(datos: bytes) -> str:
    """Decodifica un TXT (UTF-8 con respaldo Latin-1)."""
    return datos.decode("utf-8", errors="replace").strip()


def extraer_texto_pdf(datos: bytes) -> str | None:
    """Extrae el texto de un PDF con pypdf (respaldo cuando el LLM no acepta PDF inline)."""
    try:
        from pypdf import PdfReader  # import perezoso: no rompe si falta el paquete

        lector = PdfReader(BytesIO(datos))
        paginas = [(pagina.extract_text() or "") for pagina in lector.pages[:10]]
        return "\n".join(paginas).strip() or None
    except Exception:
        return None


def a_parte_gemini(mime: str, datos: bytes) -> dict:
    """Parte inline en Base64 para la API de Gemini (imágenes, PDFs y audio)."""
    mime = _normalizar_mime(mime)
    return {
        "inline_data": {
            # Gemini nombra el MP3 como audio/mp3
            "mime_type": "audio/mp3" if mime == "audio/mpeg" else mime,
            "data": base64.b64encode(datos).decode("ascii"),
        }
    }


def a_parte_openai(mime: str, datos: bytes) -> dict | None:
    """Parte de imagen (data URI) para GPT-4o. PDFs → None (se usa el texto extraído)."""
    mime = _normalizar_mime(mime)
    if not mime.startswith("image/"):
        return None
    b64 = base64.b64encode(datos).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}


def preparar_adjuntos(adjuntos: list[dict]) -> list[dict]:
    """
    Valida y normaliza la lista de adjuntos crudos del payload
    ([{nombre, mime, base64}], máx. MAX_ARCHIVOS).

    Retorna, por cada adjunto válido:
      {nombre, mime, datos (bytes), tamano, sha256, texto_extraido}
    """
    if len(adjuntos) > settings.MAX_ARCHIVOS:
        raise AdjuntoInvalidoError(
            f"Máximo {settings.MAX_ARCHIVOS} archivos por reporte.",
            codigo="peso",
        )

    preparados = []
    for adjunto in adjuntos:
        nombre = (adjunto.get("nombre") or "archivo").strip()[:120]
        mime = _normalizar_mime(adjunto.get("mime", ""))
        datos = validar_adjunto(nombre, mime, adjunto.get("base64", ""))

        texto_extraido = None
        if mime == "text/plain":
            texto_extraido = extraer_texto_txt(datos)
        elif mime == "application/pdf":
            texto_extraido = extraer_texto_pdf(datos)

        preparados.append({
            "nombre": nombre,
            "mime": mime,
            "datos": datos,
            "tamano": len(datos),
            "sha256": hashlib.sha256(datos).hexdigest(),
            "texto_extraido": texto_extraido,
        })

    return preparados


def resumen_evidencia(adjuntos_preparados: list[dict]) -> str:
    """Huella textual de los archivos adjuntos para incluirla en el certificado SHA-256."""
    return "\n".join(f"{a['sha256']}:{a['nombre']}" for a in adjuntos_preparados)
