"""
Canal de denuncia web.

POST /api/reporte-web recibe los reportes del formulario de React (texto,
archivos adjuntos y notas de voz en Base64) y ejecuta el flujo completo de
services.procesamiento: IA multimodal, verificación en fuentes abiertas,
confianza, plan de acción, certificado encadenado y anclaje en Bitcoin.
"""
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.limite import limitar_por_ip
from app.services.anonimizar import seudonimo
from app.services.archivos import AdjuntoInvalidoError, preparar_adjuntos
from app.services.geolocalizacion import UPZ_BOSA, dentro_de_bosa, validar_o_asignar
from app.services.procesamiento import procesar_reporte

router = APIRouter()

# Mapeo de código de error de adjunto → status HTTP
_STATUS_ADJUNTO = {"peso": 413, "formato": 415, "corrupto": 400}

class Adjunto(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=120)
    mime: str = Field(..., min_length=3, max_length=100)
    base64: str = Field(..., min_length=1, description="Contenido del archivo en Base64")


class ReporteWeb(BaseModel):
    mensaje: str = Field("", max_length=5000, description="Texto del mensaje sospechoso")
    adjuntos: list[Adjunto] = Field(
        default_factory=list,
        max_length=settings.MAX_ARCHIVOS,
        description=f"Máximo {settings.MAX_ARCHIVOS} archivos (PDF, TXT, PNG, JPEG, WEBP, audio)",
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
async def reportar_mensaje(reporte: ReporteWeb, request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    limitar_por_ip(ip or "desconocida")

    mensaje = reporte.mensaje.strip()
    adjuntos_crudos = [a.model_dump() for a in reporte.adjuntos]
    if len(mensaje) < 10 and not adjuntos_crudos:
        raise HTTPException(status_code=400, detail="Envía al menos un mensaje (10 caracteres), un archivo o una nota de voz.")

    try:
        adjuntos = preparar_adjuntos(adjuntos_crudos)
    except AdjuntoInvalidoError as error:
        raise HTTPException(status_code=_STATUS_ADJUNTO.get(error.codigo, 400), detail=str(error))

    nombre = (reporte.upz or reporte.barrio or "").strip().lower()
    upz = next((u for u in UPZ_BOSA if u.lower() == nombre), None)
    gps_en_bosa = reporte.lat is not None and reporte.lng is not None and dentro_de_bosa(reporte.lat, reporte.lng)
    lat, lng = validar_o_asignar(reporte.lat, reporte.lng, upz, seed=f"{mensaje}{time.time()}")

    resultado = await procesar_reporte(
        mensaje=mensaje, adjuntos=adjuntos, canal="web",
        # El reporte web es anónimo: el seudónimo de la IP solo sirve para contar abusos
        reportante=seudonimo(f"ip:{ip}") if ip else "anonimo",
        upz=upz or "Bosa Central", lat=lat, lng=lng,
    )
    return {
        **resultado,
        "upz": upz or "Bosa Central",
        "barrio": upz or "Bosa Central",
        "lat": lat,
        "lng": lng,
        "ubicacion_dispositivo_en_bosa": gps_en_bosa,
    }
