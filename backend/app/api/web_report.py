"""
Canal de denuncia web.

POST /api/reporte-web recibe los reportes del formulario de React
(texto + archivos adjuntos en Base64), los procesa con el agente LLM
multimodal, los cruza contra fuentes abiertas, genera el certificado
SHA-256 (incluyendo la huella de los adjuntos) y guarda la evidencia
en Firebase Firestore.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.analizador import evaluar_fraude
from app.services.archivos import AdjuntoInvalidoError, preparar_adjuntos, resumen_evidencia
from app.services.certificado import generar_certificado
from app.services.firebase_db import guardar_alerta
from app.services.geolocalizacion import UPZ_BOSA, BARRIOS_BOSA, validar_o_asignar, dentro_de_bosa
from app.services.verificador import verificar_mensaje, riesgo_verificado

router = APIRouter()

# Mapeo de código de error de adjunto → status HTTP
_STATUS_ADJUNTO = {"peso": 413, "formato": 415, "corrupto": 400}


class Adjunto(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    mime: str = Field(..., min_length=3, max_length=100)
    base64: str = Field(..., min_length=1, description="Contenido del archivo en Base64")


class ReporteWeb(BaseModel):
    mensaje: str = Field("", max_length=5000,
                         description="Texto del mensaje sospechoso")
    adjuntos: list[Adjunto] = Field(
        default_factory=list,
        max_length=settings.MAX_ARCHIVOS,
        description=f"Máximo {settings.MAX_ARCHIVOS} archivos (PDF, TXT, PNG, JPEG)",
    )
    upz: str | None = Field(None, description="UPZ de Bosa: Apogeo, Bosa Occidental, Bosa Central, El Porvenir o Tintal Sur")
    barrio: str | None = Field(None, description="Campo legado para compatibilidad con UPZ")
    lat: float | None = None
    lng: float | None = None
    canal: str = "web"


@router.get("/reporte-web")
@router.get("/reporte-web/")
def info_reporte_web():
    return {
        "status": "online",
        "metodo": "POST",
        "detalle": "Canal de denuncia web activo. Envía un POST con el JSON del reporte.",
    }


@router.post("/reporte-web")
@router.post("/reporte-web/")
async def reportar_mensaje(reporte: ReporteWeb):
    mensaje = reporte.mensaje.strip()
    adjuntos_crudos = [a.model_dump() for a in reporte.adjuntos]

    if len(mensaje) < 10 and not adjuntos_crudos:
        raise HTTPException(
            status_code=400,
            detail="Envía al menos un mensaje (10 caracteres) o un archivo adjunto.",
        )

    # 1. Validación de adjuntos (formato, magic bytes, peso) → 413/415/400
    try:
        adjuntos = preparar_adjuntos(adjuntos_crudos)
    except AdjuntoInvalidoError as error:
        raise HTTPException(status_code=_STATUS_ADJUNTO.get(error.codigo, 400),
                            detail=str(error))

    # 2. Detección avanzada con IA (agente multimodal: texto + archivos)
    analisis = await evaluar_fraude(mensaje, adjuntos)

    # 3. Verificación en fuentes abiertas
    verificacion = verificar_mensaje(mensaje)
    nivel_riesgo = riesgo_verificado(verificacion, analisis["nivel_riesgo"])

    # 4. Certificado trazable e inmanipulable (SHA-256 del texto + huellas de archivos)
    fecha = datetime.now(timezone.utc).isoformat()
    evidencia = resumen_evidencia(adjuntos)
    certificado = generar_certificado(f"{mensaje}\n{evidencia}", nivel_riesgo, fecha)

    # 5. Georreferenciación: validar si la ubicación del dispositivo está dentro de Bosa
    nombre_solicitado = (reporte.upz or reporte.barrio or "").strip() or None
    upz_asignada = None
    if nombre_solicitado:
        upz_asignada = next((u for u in UPZ_BOSA if u.lower() == nombre_solicitado.lower()), None)

    # Si el cliente envió coordenadas del dispositivo, verificar si caen estrictamente en Bosa
    gps_en_bosa = False
    if reporte.lat is not None and reporte.lng is not None:
        gps_en_bosa = dentro_de_bosa(reporte.lat, reporte.lng)

    # validar_o_asignar: si el GPS está en Bosa lo preserva; si no, usa la UPZ (o centro)
    lat, lng = validar_o_asignar(reporte.lat, reporte.lng, upz_asignada, seed=certificado)

    # 6. Guardar evidencia en Firebase
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
        upz=upz_asignada or "Bosa Central",
        barrio=upz_asignada or "Bosa Central",
        motor=analisis.get("motor", ""),
        adjuntos=[{
            "nombre": a["nombre"],
            "mime": a["mime"],
            "tamano": a["tamano"],
            "sha256": a["sha256"],
        } for a in adjuntos],
    )

    return {
        "id": doc_id,
        "nivel_riesgo": nivel_riesgo,
        "flags": analisis["flags"],
        "resumen": analisis["resumen"],
        "verificacion": verificacion,
        "certificado": certificado,
        "fecha": fecha,
        "upz": upz_asignada or "Bosa Central",
        "barrio": upz_asignada or "Bosa Central",
        "lat": lat,
        "lng": lng,
        "ubicacion_dispositivo_en_bosa": gps_en_bosa,
        "motor": analisis.get("motor", ""),
        "adjuntos_analizados": len(adjuntos),
        "adjuntos": [{
            "nombre": a["nombre"],
            "mime": a["mime"],
            "tamano": a["tamano"],
            "sha256": a["sha256"],
        } for a in adjuntos],
    }
