"""
Motor de detección de fraude con IA.

Integra un LLM real (Google Gemini u OpenAI GPT) vía HTTP para analizar el
texto del mensaje, identificar patrones de phishing / suplantación y devolver
un JSON estructurado con:
    - nivel_riesgo: int (0-100)
    - flags: list[str]  (ej: "Presión de tiempo", "Enlace sospechoso")
    - resumen: str      (explicación breve para el ciudadano)

Si el proveedor no está configurado o falla, se usa un análisis heurístico
local como fallback para que el servicio nunca quede inoperativo.
"""
import json
import re
import httpx

from app.core.config import settings

PROMPT_SISTEMA = """
Eres el motor de inteligencia artificial del "Escudo Comunitario", un sistema
de prevención de fraude digital para la localidad de Bosa (Bogotá, Colombia).

Recibirás el texto de un mensaje sospechoso (WhatsApp, SMS o redes sociales).
Tu tarea es identificar patrones de phishing, suplantación de entidades
(bancos, Policía, DATATUR, Nequi, Bancolombia, Daviplata, etc.), sorteos
falsos, extorsión y fraude con pagos por transferencia o depósito.

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
"Enlace acortado", "Errores y urgencia atípica", "Amenaza o extorsión".
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


# --------------------------------------------------------------------------- #
# Proveedores LLM
# --------------------------------------------------------------------------- #

async def _analizar_con_gemini(texto: str) -> dict | None:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": f"{PROMPT_SISTEMA}\n\nMENSAJE:\n{texto}"}]}],
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
            headers={"x-goog-api-key": settings.GEMINI_API_KEY or ""},
        )
        resp.raise_for_status()
        data = resp.json()
        return _extraer_json(data["candidates"][0]["content"]["parts"][0]["text"])


async def _analizar_con_openai(texto: str) -> dict | None:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": f"MENSAJE:\n{texto}"},
        ],
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY or ''}"},
        )
        resp.raise_for_status()
        return _extraer_json(resp.json()["choices"][0]["message"]["content"])


# --------------------------------------------------------------------------- #
# Fallback heurístico local
# --------------------------------------------------------------------------- #

def _analisis_heuristico(texto: str) -> dict:
    texto_lower = texto.lower()
    score, flags = 0, []
    for patron, flag, peso in _PATRONES_FALLBACK:
        if re.search(patron, texto_lower, flags=re.IGNORECASE):
            score += peso
            flags.append(flag)
    return {
        "nivel_riesgo": max(0, min(100, score)),
        "flags": flags,
        "resumen": "Análisis local de respaldo (sin IA). "
                   "Verifica la información en fuentes oficiales antes de actuar.",
        "motor": "heuristico",
    }


# --------------------------------------------------------------------------- #
# Interfaz pública
# --------------------------------------------------------------------------- #

async def evaluar_fraude(texto: str) -> dict:
    """Analiza el mensaje con el LLM configurado y retorna el veredicto estructurado."""
    texto = (texto or "").strip()
    if not texto:
        return dict(_ANALISIS_FALLBACK, motor="vacio")

    proveedor = settings.LLM_PROVIDER
    try:
        if proveedor == "gemini" and settings.GEMINI_API_KEY:
            resultado = await _analizar_con_gemini(texto)
        elif proveedor == "openai" and settings.OPENAI_API_KEY:
            resultado = await _analizar_con_openai(texto)
        elif proveedor == "heuristico":
            return _analisis_heuristico(texto)
        else:
            # Sin API key configurada: se degrada al análisis local
            return _analisis_heuristico(texto)
        if resultado is not None:
            return _sanitizar_analisis(resultado)
    except Exception:
        # Cualquier error del proveedor no debe tumbar el servicio
        pass

    fallback = _analisis_heuristico(texto)
    fallback["motor"] = "heuristico (respaldo por error del LLM)"
    return fallback
