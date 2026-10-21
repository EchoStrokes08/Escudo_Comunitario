"""
Canal de denuncia web.

POST /api/reporte-web recibe los reportes del formulario de React,
los procesa con el LLM, los cruza contra fuentes abiertas, genera el
certificado SHA-256 y guarda la evidencia en Firebase Firestore.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.analizador import evaluar_fraude
from app.services.certificado import generar_certificado
from app.services.firebase_db import guardar_alerta
from app.services.geolocalizacion import BARRIOS_BOSA, obtener_coordenadas
from app.services.verificador import verificar_mensaje, riesgo_verificado

router = APIRouter()


class ReporteWeb(BaseModel):
    mensaje: str = Field(..., min_length=10, max_length=5000,
                         description="Texto del mensaje sospechoso")
    barrio: str | None = Field(None, description="Barrio de la localidad de Bosa")
    lat: float | None = None
    lng: float | None = None
    canal: str = "web"


@router.post("/reporte-web")
async def reportar_mensaje(reporte: ReporteWeb):
    mensaje = reporte.mensaje.strip()
    if len(mensaje) < 10:
        raise HTTPException(status_code=400, detail="El mensaje es demasiado corto.")

    # 1. Detección avanzada con IA
    analisis = await evaluar_fraude(mensaje)

    # 2. Verificación en fuentes abiertas
    verificacion = verificar_mensaje(mensaje)
    nivel_riesgo = riesgo_verificado(verificacion, analisis["nivel_riesgo"])

    # 3. Certificado trazable e inmanipulable (SHA-256)
    fecha = datetime.now(timezone.utc).isoformat()
    certificado = generar_certificado(mensaje, nivel_riesgo, fecha)

    # 4. Georreferenciación en la localidad de Bosa
    barrio = (reporte.barrio or "").strip().title() or None
    if barrio and barrio not in BARRIOS_BOSA:
        barrio = None  # ignora barrios fuera de la localidad

    if reporte.lat is not None and reporte.lng is not None:
        lat, lng = round(reporte.lat, 6), round(reporte.lng, 6)
    else:
        lat, lng = obtener_coordenadas(barrio, seed=certificado)

    # 5. Guardar evidencia en Firebase
    doc_id = guardar_alerta(
        "web",
        mensaje,
        nivel_riesgo,
        certificado,
        canal=reporte.canal,
        flags=analisis["flags"],
        resumen=analisis["resumen"],
        verificacion=verificacion,
        lat=lat,
        lng=lng,
        barrio=barrio,
        motor=analisis.get("motor", ""),
    )

    return {
        "id": doc_id,
        "nivel_riesgo": nivel_riesgo,
        "flags": analisis["flags"],
        "resumen": analisis["resumen"],
        "verificacion": verificacion,
        "certificado": certificado,
        "fecha": fecha,
        "barrio": barrio or "Bosa Centro",
        "motor": analisis.get("motor", ""),
    }
