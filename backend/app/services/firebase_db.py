import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from datetime import datetime

# Evitar doble inicialización en Vercel
if not firebase_admin._apps:
    if settings.FIREBASE_CREDENTIALS_DICT:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_DICT)
    else:
        # Fallback local
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def guardar_alerta(telefono: str, mensaje: str, riesgo: int, certificado: str):
    doc_ref = db.collection("alertas_bosa").document()
    doc_ref.set({
        "telefono": telefono,
        "mensaje_original": mensaje,
        "nivel_riesgo": riesgo,
        "certificado": certificado,
        "fecha": datetime.now().isoformat(),
        "estado": "verificado"
    })
    return doc_ref.id