"""
Soporte de archivos adjuntos (multimodal).

Valida los adjuntos que llegan del frontend o de Twilio (WhatsApp) y los
normaliza para que el agente LLM pueda procesarlos:
  - imágenes (PNG, JPEG) → parte visual en Base64
  - PDF                  → parte PDF inline (Gemini) o texto extraído (OpenAI)
  - TXT                  → texto plano inyectado al prompt

Límites y formatos controlados por variables de entorno (MAX_PESO_MB, MAX_ARCHIVOS).
"""
import base64
import binascii
import hashlib
from io import BytesIO

from app.core.config import settings

MIME_SOPORTADOS = {"image/png", "image/jpeg", "application/pdf", "text/plain"}

# Firmas binarias (magic bytes) para validar que el archivo es lo que dice ser
_MAGIC_BYTES = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "application/pdf": (b"%PDF-",),
    "text/plain": (),  # texto plano sin firma binaria
}

MAX_PESO_BYTES = settings.MAX_PESO_MB * 1024 * 1024


class AdjuntoInvalidoError(Exception):
    """Error de validación de adjunto.

    codigo: "formato" | "peso" | "corrupto"
    """

    def __init__(self, mensaje: str, codigo: str = "formato"):
        super().__init__(mensaje)
        self.codigo = codigo


def _normalizar_mime(mime: str) -> str:
    return (mime or "").lower().split(";")[0].strip()


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

    if len(datos) > MAX_PESO_BYTES:
        raise AdjuntoInvalidoError(
            f"'{nombre}': el archivo pesa {len(datos) / 1_048_576:.1f} MB y el máximo es "
            f"{settings.MAX_PESO_MB} MB. Comprime la imagen o adjunta un archivo más pequeño.",
            codigo="peso",
        )

    firmas = _MAGIC_BYTES.get(mime, ())
    if firmas and not any(datos.startswith(f) for f in firmas):
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
    """Parte inline en Base64 para la API de Gemini (imágenes y PDFs)."""
    return {
        "inline_data": {
            "mime_type": _normalizar_mime(mime),
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
