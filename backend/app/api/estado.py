"""
GET /api/estado            Salud del servicio y de cada componente (sin secretos).
GET /api/estado?probar_ia=1  Además hace una llamada real al LLM para diagnosticar claves/modelos.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.services import firebase_db
from app.services.analizador import ESTADO_LLM, diagnosticar_llm

router = APIRouter()


@router.get("/estado")
async def estado(probar_ia: bool = False):
    resultado = {
        "servicio": "Escudo Comunitario - Bosa",
        "ia": {
            "proveedor_preferido": settings.LLM_PROVIDER,
            "modelos": {"groq": settings.GROQ_MODEL, "groq_audio": settings.GROQ_MODELO_AUDIO,
                        "gemini": settings.GEMINI_MODEL},
            "claves": {"groq": len(settings.GROQ_API_KEYS), "gemini": len(settings.GEMINI_API_KEYS),
                       "openai": len(settings.OPENAI_API_KEYS)},
            "ultimo_uso": ESTADO_LLM,
        },
        "fuentes_abiertas": {
            "rdap": "activa",
            "suplantacion_de_marca": "activa",
            "acortadores": "activa",
            "historial_comunitario": "activa",
            "urlhaus": "activa" if settings.URLHAUS_AUTH_KEY else "no configurada",
            "google_safe_browsing": "activa" if settings.GOOGLE_SAFE_BROWSING_KEY else "no configurada",
        },
        "whatsapp": {
            "firma_twilio": bool(settings.TWILIO_AUTH_TOKEN and settings.TWILIO_VALIDAR_FIRMA),
            "alertas_a_lideres": bool(settings.LIDERES_WHATSAPP and settings.TWILIO_WHATSAPP_FROM),
        },
        "autoridades": bool(settings.AUTORIDADES_TOKEN),
    }
    try:
        cadena = firebase_db.estado_cadena()
        resultado["cadena"] = {"bloques": cadena.get("altura", -1) + 1, "ultimo_hash": cadena.get("ultimo_hash")}
    except Exception as error:
        resultado["cadena"] = {"error": type(error).__name__}
    if probar_ia:
        resultado["ia"]["prueba"] = await diagnosticar_llm()
    return resultado
