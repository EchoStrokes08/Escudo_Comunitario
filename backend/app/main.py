from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import whatsapp

app = FastAPI(title="API Escudo Comunitario")

# Configuración estricta de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])

@app.get("/")
def health_check():
    return {"status": "online", "servicio": "Escudo Comunitario - Bosa"}