from fastapi import APIRouter, Form, Response
from app.services.analizador import evaluar_fraude
from app.services.firebase_db import guardar_alerta
from twilio.twiml.messaging_response import MessagingResponse

router = APIRouter()

@router.post("/webhook")
async def recibir_whatsapp(From: str = Form(...), Body: str = Form(...)):
    # 1. Analizar
    riesgo, certificado = evaluar_fraude(Body)
    
    # 2. Guardar evidencia
    guardar_alerta(From, Body, riesgo, certificado)
    
    # 3. Formatear la respuesta XML que Twilio entiende
    respuesta = MessagingResponse()
    if riesgo >= 50:
        respuesta.message(f"⚠️ *Alerta de Riesgo: {riesgo}%*\nPatrones de fraude detectados en este mensaje. No ingreses a los enlaces.\n\n🛡️ Certificado de reporte: {certificado}")
    else:
        respuesta.message(f"✅ Riesgo bajo ({riesgo}%). Mantente alerta y verifica fuentes oficiales.\n\n🛡️ Certificado de reporte: {certificado}")
        
    return Response(content=str(respuesta), media_type="application/xml")