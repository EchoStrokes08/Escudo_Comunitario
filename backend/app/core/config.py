import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Carga las variables de entorno buscando en múltiples rutas (backend/.env, backend/env, root/.env, root/env)
_app_dir = Path(__file__).resolve().parent.parent  # backend/app
_backend_dir = _app_dir.parent                     # backend
_root_dir = _backend_dir.parent                    # raíz del proyecto

for _candidate in [
    _backend_dir / ".env",
    _backend_dir / "env",
    _root_dir / ".env",
    _root_dir / "env",
]:
    if _candidate.exists() and _candidate.is_file():
        load_dotenv(_candidate)

load_dotenv()  # Fallback para el CWD actual


def _parse_bool(valor: str | None, default: bool = False) -> bool:
    if valor is None:
        return default
    return valor.strip().lower() in ("1", "true", "yes", "on")


def _parse_lista(valor: str | None) -> list[str]:
    """Lista separada por comas (ignora espacios y elementos vacíos)."""
    return [v.strip() for v in (valor or "").split(",") if v.strip()]


class Settings:
    # --- Twilio (canal WhatsApp) ---
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

    # --- Firebase ---
    firebase_env = os.getenv("FIREBASE_CREDENTIALS")
    FIREBASE_CREDENTIALS_DICT = None

    if firebase_env:
        try:
            FIREBASE_CREDENTIALS_DICT = json.loads(firebase_env)
        except Exception:
            # Si no es JSON raw, intentar como ruta de archivo (relativa a cwd, backend o root)
            posibles_rutas = [
                Path(firebase_env),
                _backend_dir / firebase_env,
                _root_dir / firebase_env,
            ]
            for p in posibles_rutas:
                if p.exists() and p.is_file():
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            FIREBASE_CREDENTIALS_DICT = json.load(f)
                        break
                    except Exception:
                        pass

    # Si aún no se encontró, buscar directamente serviceAccountKey.json o cualquier clave AdminSDK
    if not FIREBASE_CREDENTIALS_DICT:
        rutas_clave = [
            _backend_dir / "serviceAccountKey.json",
            _root_dir / "serviceAccountKey.json",
            Path("serviceAccountKey.json"),
            Path("backend/serviceAccountKey.json"),
            *list(_backend_dir.glob("*adminsdk*.json")),
            *list(_root_dir.glob("*adminsdk*.json")),
        ]
        for r in rutas_clave:
            if r.exists() and r.is_file():
                try:
                    with open(r, "r", encoding="utf-8") as f:
                        FIREBASE_CREDENTIALS_DICT = json.load(f)
                    break
                except Exception:
                    continue

    # --- LLM (detección avanzada) ---
    # Proveedor seleccionable: "gemini" | "openai" | "heuristico"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    # Admiten varias claves separadas por comas: si una se queda sin cuota o falla, se usa la siguiente
    GEMINI_API_KEYS = _parse_lista(os.getenv("GEMINI_API_KEY"))
    # Modelo preferido; si no existe (p. ej. gemini-1.5-flash, ya retirado) se prueban
    # los de GEMINI_MODELOS_RESPALDO en orden y se recuerda el primero que funcione
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
    GEMINI_MODELOS_RESPALDO = _parse_lista(
        os.getenv("GEMINI_MODELOS_RESPALDO", "gemini-3.5-flash,gemini-flash-lite-latest,gemini-flash-latest,gemini-3.8-flash")
    )

    OPENAI_API_KEYS = _parse_lista(os.getenv("OPENAI_API_KEY"))
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Segundos máximos de espera por intento y en total antes de caer al análisis heurístico
    LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "15"))
    LLM_PRESUPUESTO = float(os.getenv("LLM_PRESUPUESTO", "30"))

    # --- Archivos adjuntos (multimodal) ---
    MAX_ARCHIVOS = int(os.getenv("MAX_ARCHIVOS", "3"))
    MAX_PESO_MB = int(os.getenv("MAX_PESO_MB", "2"))
    # Notas de voz (WhatsApp ogg / grabación web wav): ~60 s caben en 4 MB
    MAX_PESO_AUDIO_MB = int(os.getenv("MAX_PESO_AUDIO_MB", "4"))

    # --- Verificación en fuentes abiertas ---
    # Tiempo máximo (s) de cada consulta externa: RDAP, URLhaus, Safe Browsing, acortadores
    VERIFICACION_TIMEOUT = float(os.getenv("VERIFICACION_TIMEOUT", "4"))
    # Opcionales: sin clave la fuente se omite y se informa como "no configurada"
    URLHAUS_AUTH_KEY = os.getenv("URLHAUS_AUTH_KEY")
    GOOGLE_SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY")

    # --- Registro trazable (cadena de hashes + OpenTimestamps) ---
    OTS_CALENDARIOS = _parse_lista(os.getenv(
        "OTS_CALENDARIOS",
        "https://a.pool.opentimestamps.org,https://b.pool.opentimestamps.org,https://a.pool.eternitywall.com",
    ))
    OTS_TIMEOUT = float(os.getenv("OTS_TIMEOUT", "4"))

    # --- Privacidad ---
    # Sal para seudonimizar el teléfono del reportante (sha256(sal + número)). Cámbiala en producción.
    SAL_SEUDONIMO = os.getenv("SAL_SEUDONIMO", "escudo-comunitario-bosa")

    # --- Twilio extra ---
    # Si TWILIO_AUTH_TOKEN existe, se valida la firma X-Twilio-Signature (desactivable para pruebas)
    TWILIO_VALIDAR_FIRMA = _parse_bool(os.getenv("TWILIO_VALIDAR_FIRMA"), default=True)
    # URL pública exacta configurada en Twilio (si el proxy cambia host/protocolo)
    TWILIO_WEBHOOK_URL = os.getenv("TWILIO_WEBHOOK_URL")
    # Remitente para alertas salientes, ej: whatsapp:+14155238886 (sandbox)
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")

    # --- Alertas comunitarias (brotes por UPZ) ---
    # Números de líderes comunitarios separados por comas: whatsapp:+57300...
    LIDERES_WHATSAPP = _parse_lista(os.getenv("LIDERES_WHATSAPP"))
    BROTE_MINIMO = int(os.getenv("BROTE_MINIMO", "3"))          # reportes del mismo tipo en la UPZ
    BROTE_VENTANA_HORAS = int(os.getenv("BROTE_VENTANA_HORAS", "48"))

    # --- Vista de autoridades ---
    # Token compartido con Policía/Fiscalía/organizaciones para consultar casos completos
    AUTORIDADES_TOKEN = os.getenv("AUTORIDADES_TOKEN")

    # --- CORS ---
    # Lista separada por comas. Ej: https://escudo-comunitario.vercel.app,http://localhost:5173
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

    # --- API pública (para construir respuestas enlaces) ---
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    # URL pública del frontend (enlaces de certificados y QR)
    APP_URL = os.getenv("APP_URL", "https://escudocomunitario.vercel.app").rstrip("/")

    # Controla si se permite credenciales en CORS (no permitido con "*")
    ALLOW_CREDENTIALS = _parse_bool(os.getenv("ALLOW_CREDENTIALS"), default=False)


settings = Settings()
