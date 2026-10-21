import os
import json
from dotenv import load_dotenv

# Carga las variables de entorno del archivo .env (local) o del entorno de Vercel.
# Nunca se hardcodean secretos aquí: solo se leen desde variables de entorno.
load_dotenv()


def _parse_bool(valor: str | None, default: bool = False) -> bool:
    if valor is None:
        return default
    return valor.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # --- Twilio (canal WhatsApp) ---
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

    # --- Firebase ---
    firebase_env = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_env:
        FIREBASE_CREDENTIALS_DICT = json.loads(firebase_env)
    else:
        FIREBASE_CREDENTIALS_DICT = None

    # --- LLM (detección avanzada) ---
    # Proveedor seleccionable: "gemini" | "openai" | "heuristico"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Segundos máximos de espera al LLM antes de caer al análisis heurístico
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "15"))

    # --- CORS ---
    # Lista separada por comas. Ej: https://escudo-comunitario.vercel.app,http://localhost:5173
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    # --- API pública (para construir respuestas enlaces) ---
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

    # Controla si se permite credenciales en CORS (no permitido con "*")
    ALLOW_CREDENTIALS = _parse_bool(os.getenv("ALLOW_CREDENTIALS"), default=False)


settings = Settings()
