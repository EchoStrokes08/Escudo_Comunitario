from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import whatsapp, web_report
from app.core.config import settings

app = FastAPI(title="API Escudo Comunitario")

# Configuración de CORS desde variables de entorno (CORS_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS and settings.CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(web_report.router, prefix="/api", tags=["Reporte Web"])


@app.get("/")
def health_check():
    return {"status": "online", "servicio": "Escudo Comunitario - Bosa"}
