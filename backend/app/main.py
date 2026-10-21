import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import autoridades, estado, verificacion, whatsapp, web_report
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="API Escudo Comunitario", docs_url="/api/docs", openapi_url="/api/openapi.json")

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
app.include_router(verificacion.router, prefix="/api", tags=["Verificación y cadena"])
app.include_router(autoridades.router, prefix="/api", tags=["Autoridades"])
app.include_router(estado.router, prefix="/api", tags=["Estado"])


@app.get("/")
def health_check():
    return {"status": "online", "servicio": "Escudo Comunitario - Bosa"}
