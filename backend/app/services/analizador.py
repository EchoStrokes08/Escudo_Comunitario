"""
Agente de detección de fraude multimodal.

Integra un LLM real (Google Gemini como principal, OpenAI GPT-4o como
respaldo) vía HTTP para analizar texto, imágenes (capturas de chats,
facturas falsas) y PDFs. Devuelve un JSON estructurado con:
    - nivel_riesgo: int (0-100)
    - flags: list[str]  (ej: "Presión de tiempo", "Enlace sospechoso")
    - resumen: str      (explicación breve para el ciudadano)

Si el proveedor no está configurado o falla, se usa un análisis heurístico
local sobre el texto (incluido el texto extraído de TXT/PDF) como fallback
para que el servicio nunca quede inoperativo.
"""
import json
import re
import httpx

from app.core.config import settings
from app.services.archivos import (
    a_parte_gemini,
    a_parte_openai,
)

PROMPT_SISTEMA = """
Eres el motor de inteligencia artificial del "Escudo Comunitario", un sistema
de prevención de fraude digital para la localidad de Bosa (Bogotá, Colombia).

Recibirás el texto de un mensaje sospechoso (WhatsApp, SMS o redes sociales)
y, opcionalmente, archivos adjuntos: capturas de pantalla, facturas en PDF o
archivos de texto. Tu tarea es identificar patrones de phishing, suplantación
de entidades (bancos, Policía, DATATUR, Nequi, Bancolombia, Daviplata, etc.),
sorteos falsos, extorsión y fraude con pagos por transferencia o depósito.

INSTRUCCIONES MULTIMODAL:
- Si recibes una captura de pantalla de un chat (WhatsApp, SMS, redes), aplica
  OCR visual sobre la imagen: lee el texto completo, identifica el emisor, los
  enlaces, los números de teléfono y las cuentas de pago visibles.
- Si recibes un PDF o una imagen de una factura, notificación o supuesto premio,
  identifica la entidad suplantada, los datos de pago solicitados y las señales
  de urgencia o presión.
- El usuario puede escribir texto adicional junto al archivo: crúzalo con lo
  leído en el archivo. El nivel_riesgo y los flags deben reflejar la evidencia
  COMBINADA de ambas fuentes (texto del usuario + contenido del adjunto).

Responde EXCLUSIVAMENTE con un objeto JSON válido, sin markdown, sin texto
adicional, con esta forma exacta:
{
  "nivel_riesgo": <entero de 0 a 100>,
  "flags": ["<patrón detectado>", ...],
  "resumen": "<una o dos frases en español claro para el ciudadano>"
}

Reglas para nivel_riesgo:
- 0-30: mensaje legítimo o sin indicios de fraude.
- 31-69: indicios sospechosos (urgenca, premios, links, datos financieros).
- 70-100: fraude muy probable (suplantación + presión + dato sensible o dinero).

Ejemplos de flags válidos: "Presión de tiempo", "Enlace sospechoso",
"Premio o sorteo falso", "Suplantación de entidad oficial",
"Solicitud de datos financieros", "Solicitud de dinero o depósito",
"Enlace acortado", "Errores y urgencia atípica", "Amenaza o extorsión",
"OCR: enlace no coincidente con la entidad", "Factura o notificación falsa".
""".strip()

_ANALISIS_FALLBACK = {
    "nivel_riesgo": 0,
    "flags": [],
    "resumen": "Sin indicios claros de fraude detectados por el análisis local.",
}

_PATRONES_FALLBACK = [
    # (expresión regular, flag, peso)
    (r"\b(urgente|inmediat?amente|ahora mismo|en los? pr[oó]ximos?\s+\d+\s*(min|hora)|se\s+cancelar[aá]|última\s+advertencia)\b",
     "Presión de tiempo", 25),
    (r"(https?://|www\.|bit\.ly|tinyurl|t\.co|clck|wa\.me)", "Enlace sospechoso", 25),
    (r"\b(premio|ganador|sorteo|regalo|bono de|million(es)?|iphone|viaje gratis)\b",
     "Premio o sorteo falso", 20),
    (r"\b(nequi|daviplata|bancolombia|davivienda|bbva|banco\s+de\s+occidente|bogota\.com|rapipay|colpatria)\b",
     "Posible suplantación de entidad", 15),
    (r"\b(consign(a|ar|ación)|transfer(ir|encia)|dep(osit|ósito)|env(í|i)ar dinero|cuenta\s+(de\s+ahorros|bancaria)|cédula\s+de\s+ciudadan(í)a)\b",
     "Solicitud de dinero o datos financieros", 20),
    (r"\b(verifica(r)?\s+(tu\s+)?(cuenta|clave|contraseña|datos)|codigo?\s+de\s+seguridad|otp|clave\s+de\s+un\s+uso)\b",
     "Solicitud de credenciales o códigos", 20),
    (r"\b(polic(í|i)a|cau|cai|fiscal(í|i)a|datatur|supersalud|ministerio\s+de)\b",
     "Menciona entidad oficial (posible suplantación)", 10),
]


def _extraer_json(texto: str) -> dict | None:
    """Extrae el primer objeto JSON válido de la respuesta del LLM."""
    texto = texto.strip()
    # Quita bloque de código ```json ... ```
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        inicio, fin = texto.find("{"), texto.rfind("}")
        if inicio != -1 and fin > inicio:
            try:
                return json.loads(texto[inicio:fin + 1])
            except json.JSONDecodeError:
                return None
    return None


def _sanitizar_analisis(data: dict | None) -> dict:
    """Valida y normaliza la respuesta del LLM al contrato esperado."""
    if not isinstance(data, dict):
        return dict(_ANALISIS_FALLBACK)

    try:
        nivel = int(round(float(data.get("nivel_riesgo", 0))))
    except (TypeError, ValueError):
        nivel = 0

    flags = data.get("flags", [])
    if not isinstance(flags, list):
        flags = [str(flags)]
    flags = [str(f).strip() for f in flags if str(f).strip()][:10]

    resumen = str(data.get("resumen", "")).strip()[:400] or _ANALISIS_FALLBACK["resumen"]

    return {
        "nivel_riesgo": max(0, min(100, nivel)),
        "flags": flags,
        "resumen": resumen,
        "motor": "llm",
    }


def _texto_de_adjuntos(texto_adjuntos: list[str]) -> str:
    """Concatena el texto extraído de TXT/PDF para enriquecer el prompt."""
    bloques = [t for t in texto_adjuntos if t]
    if not bloques:
        return ""
    contenido = "\n\n".join(bloques)[:6000]
    return f"\n\nTEXTO EXTRAÍDO DE LOS ARCHIVOS ADJUNTOS:\n{contenido}"


# --------------------------------------------------------------------------- #
# Proveedores LLM (multimodal)
# --------------------------------------------------------------------------- #

async def _analizar_con_gemini(texto: str, adjuntos: list[dict] | None, clave: str) -> dict | None:
    """
    Gemini 1.5 Flash: acepta imágenes Y PDFs como partes inline en Base64
    (adjuntos ya validados por services.archivos).
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    partes = [{"text": f"{PROMPT_SISTEMA}\n\nMENSAJE DEL USUARIO:\n{texto}"}]
    for adjunto in adjuntos or []:
        partes.append(a_parte_gemini(adjunto["mime"], adjunto["datos"]))

    payload = {
        "contents": [{"parts": partes}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"x-goog-api-key": clave},
        )
        resp.raise_for_status()
        data = resp.json()
        return _extraer_json(data["candidates"][0]["content"]["parts"][0]["text"])


async def _analizar_con_openai(texto: str, adjuntos: list[dict] | None, clave: str) -> dict | None:
    """
    GPT-4o: acepta imágenes como data URIs. Los PDFs no son soportados inline,
    por lo que se envía su texto extraído (services.archivos.extraer_texto_pdf).
    """
    url = "https://api.openai.com/v1/chat/completions"

    partes: list[dict] = [{"type": "text", "text": f"MENSAJE DEL USUARIO:\n{texto}"}]
    textos_extraidos = []
    for adjunto in adjuntos or []:
        parte = a_parte_openai(adjunto["mime"], adjunto["datos"])
        if parte is not None:
            partes.append(parte)
        elif adjunto.get("texto_extraido"):
            textos_extraidos.append(
                f"[{adjunto['nombre']}]\n{adjunto['texto_extraido']}"
            )

    if textos_extraidos:
        partes[0]["text"] += _texto_de_adjuntos(textos_extraidos)

    payload = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": partes},
        ],
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {clave}"},
        )
        resp.raise_for_status()
        return _extraer_json(resp.json()["choices"][0]["message"]["content"])


# --------------------------------------------------------------------------- #
# Fallback heurístico local
# --------------------------------------------------------------------------- #

def _analisis_heuristico(texto: str, adjuntos: list[dict] | None = None) -> dict:
    """Análisis local sobre el texto del usuario + texto extraído de TXT/PDF."""
    textos = [texto]
    for adjunto in adjuntos or []:
        if adjunto.get("texto_extraido"):
            textos.append(adjunto["texto_extraido"])

    texto_lower = "\n".join(textos).lower()
    score, flags = 0, []
    for patron, flag, peso in _PATRONES_FALLBACK:
        if re.search(patron, texto_lower, flags=re.IGNORECASE):
            score += peso
            flags.append(flag)

    if adjuntos and score == 0 and not any(a.get("texto_extraido") for a in adjuntos):
        flags.append("Archivo adjunto sin analizar (se requiere IA)")
        score += 5

    return {
        "nivel_riesgo": max(0, min(100, score)),
        "flags": flags,
        "resumen": "Análisis local de respaldo (sin IA). "
                   "Verifica la información en fuentes oficiales antes de actuar.",
        "motor": "heuristico",
    }


# Cada proveedor con su función y sus claves (leídas al momento para respetar settings)
_PROVEEDORES = {
    "gemini": lambda: (_analizar_con_gemini, settings.GEMINI_API_KEYS),
    "openai": lambda: (_analizar_con_openai, settings.OPENAI_API_KEYS),
}


# --------------------------------------------------------------------------- #
# Interfaz pública
# --------------------------------------------------------------------------- #

async def evaluar_fraude(texto: str, adjuntos: list[dict] | None = None) -> dict:
    """
    Analiza el mensaje (y sus adjuntos ya validados por services.archivos.preparar_adjuntos)
    con el LLM configurado y retorna el veredicto estructurado.
    """
    texto = (texto or "").strip()
    adjuntos = adjuntos or []

    if not texto and not adjuntos:
        return dict(_ANALISIS_FALLBACK, motor="vacio")

    if settings.LLM_PROVIDER == "heuristico":
        return _analisis_heuristico(texto, adjuntos)

    # Proveedor configurado primero; el otro (si tiene claves) queda como respaldo
    orden = sorted(_PROVEEDORES, key=lambda p: p != settings.LLM_PROVIDER)
    intentos = []
    for proveedor in orden:
        analizar, claves = _PROVEEDORES[proveedor]()
        intentos.extend((analizar, clave) for clave in claves)
    if not intentos:
        # Sin API key configurada: se degrada al análisis local
        return _analisis_heuristico(texto, adjuntos)

    for analizar, clave in intentos:
        try:
            resultado = await analizar(texto, adjuntos, clave)
        except Exception:
            # Cuota agotada, clave inválida, timeout…: se prueba la siguiente clave
            continue
        if resultado is not None:
            return _sanitizar_analisis(resultado)

    fallback = _analisis_heuristico(texto, adjuntos)
    fallback["motor"] = "heuristico (respaldo por error del LLM)"
    return fallback
