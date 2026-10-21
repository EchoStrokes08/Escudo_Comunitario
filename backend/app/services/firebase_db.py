import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from datetime import datetime, timezone

# Evitar doble inicialización en Vercel
if not firebase_admin._apps:
    if settings.FIREBASE_CREDENTIALS_DICT:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_DICT)
    else:
        # Fallback local: serviceAccountKey.json en la raíz de /backend (no commitear)
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()


def guardar_alerta(
    telefono: str,
    mensaje: str,
    nivel_riesgo: int,
    certificado: str,
    *,
    canal: str = "whatsapp",
    flags: list | None = None,
    resumen: str = "",
    verificacion: dict | None = None,
    lat: float | None = None,
    lng: float | None = None,
    barrio: str | None = None,
    upz: str | None = None,
    motor: str = "",
    adjuntos: list | None = None,
) -> str:
    """Persiste un reporte en Firestore (colección alertas_bosa)."""
    upz_final = upz or barrio or "Bosa Central"
    doc_ref = db.collection("alertas_bosa").document()
    doc_ref.set({
        "telefono": telefono,
        "mensaje_original": mensaje,
        "nivel_riesgo": int(nivel_riesgo),
        "certificado": certificado,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "estado": "verificado",
        "canal": canal,
        "flags": flags or [],
        "resumen": resumen,
        "verificacion": verificacion or {},
        "lat": lat,
        "lng": lng,
        "upz": upz_final,
        "barrio": upz_final,
        "motor": motor,
        "adjuntos": adjuntos or [],  # metadatos + sha256 (sin binarios)
    })
    return doc_ref.id


def obtener_alertas(limite: int = 200) -> list[dict]:
    """Consulta los reportes más recientes (útil para paneles externos)."""
    docs = (
        db.collection("alertas_bosa")
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .limit(limite)
        .stream()
    )
    return [{"id": d.id, **d.to_dict()} for d in docs]
