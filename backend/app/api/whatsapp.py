"""
Webhook de Twilio para el canal de WhatsApp.

Twilio envía los mensajes como POST form-encoded (From, Body) y espera una
respuesta TwiML en XML con <MessagingResponse> para reenviar el veredicto
al ciudadano.
"""
from fastapi import APIRouter, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from app.services.analizador import evaluar_fraude
from app.services.certificado import generar_certificado, certificado_corto
from app.services.firebase_db import guardar_alerta
from app.services.geolocalizacion import obtener_coordenadas
from app.services.verificador import verificar_mensaje, riesgo_verificado

router = APIRouter()

# Respuesta base si Twilio llega a enviar un cuerpo vacío
SALUDO = (
    "🛡️ *Escudo Comunitario Bosa*\n"
    "Envíanos el mensaje sospechoso que recibiste y te diremos si es fraude."
)


@router.post("/webhook")
async def recibir_whatsapp(From: str = Form(...), Body: str = Form(...)):
    mensaje = (Body or "").strip()

    if not mensaje:
        respuesta = MessagingResponse()
        respuesta.message(SALUDO)
        return Response(content=str(respuesta), media_type="application/xml")

    # 1. Detección avanzada con IA (LLM con fallback heurístico)
    analisis = await evaluar_fraude(mensaje)

    # 2. Verificación en fuentes abiertas (dominios maliciosos + reportes CAI Virtual)
    verificacion = verificar_mensaje(mensaje)
    nivel_riesgo = riesgo_verificado(verificacion, analisis["nivel_riesgo"])

    # 3. Certificado inmanipulable (SHA-256)
    certificado = generar_certificado(mensaje, nivel_riesgo)

    # 4. Guardar evidencia en Firebase (georreferenciado en Bosa)
    lat, lng = obtener_coordenadas(None, seed=From)
    guardar_alerta(
        From,
        mensaje,
        nivel_riesgo,
        certificado,
        canal="whatsapp",
        flags=analisis["flags"],
        resumen=analisis["resumen"],
        verificacion=verificacion,
        lat=lat,
        lng=lng,
        motor=analisis.get("motor", ""),
    )

    # 5. Formatear la respuesta XML que Twilio entiende
    respuesta = MessagingResponse()
    corto = certificado_corto(certificado)

    if verificacion["arriesgado"]:
        detalle = verificacion["hallazgos"][0]
        respuesta.message(
            f"🚨 *PELIGRO ALTO: {nivel_riesgo}%*\n"
            f"Tu mensaje coincide con reportes de fraude:\n"
            f"• {detalle['valor']} — {detalle['detalle']}\n\n"
            f"🔒 Certificado: {corto}…"
        )
    elif nivel_riesgo >= 50:
        flags_txt = "\n".join(f"• {f}" for f in analisis["flags"][:3])
        respuesta.message(
            f"⚠️ *Alerta de Riesgo: {nivel_riesgo}%*\n"
            f"Patrones de fraude detectados. No ingreses a los enlaces ni compartas datos.\n"
            f"{flags_txt}\n\n"
            f"🛡️ Certificado de reporte: {corto}…"
        )
    else:
        respuesta.message(
            f"✅ *Riesgo bajo ({nivel_riesgo}%)*\n"
            f"{analisis['resumen']}\n\n"
            f"🛡️ Certificado de reporte: {corto}…"
        )

    return Response(content=str(respuesta), media_type="application/xml")
