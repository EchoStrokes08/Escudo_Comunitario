"""
Alerta temprana comunitaria.

Si en una UPZ se acumulan BROTE_MINIMO reportes de riesgo medio/alto del mismo
tipo de fraude en BROTE_VENTANA_HORAS, se publica una alerta en el panel
(colección alertas_comunitarias) y, si hay líderes configurados, se les avisa
por WhatsApp. Cada combinación UPZ + tipo alerta como máximo una vez al día.
"""
import logging
import re

from app.core.config import settings
from app.services import firebase_db
from app.services.orientacion import nombre_tipo

log = logging.getLogger("escudo.alertas")


def _clave(upz: str, tipo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{upz}-{tipo}".lower()).strip("-")


def _avisar_lideres(texto: str) -> int:
    if not (settings.LIDERES_WHATSAPP and settings.TWILIO_WHATSAPP_FROM
            and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        return 0
    from twilio.rest import Client

    cliente = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    enviados = 0
    for destino in settings.LIDERES_WHATSAPP:
        destino = destino if destino.startswith("whatsapp:") else f"whatsapp:{destino}"
        try:
            cliente.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, to=destino, body=texto)
            enviados += 1
        except Exception as error:
            log.warning("No se pudo avisar a un líder: %s", error)
    return enviados


def revisar_brote(upz: str, tipo: str) -> dict | None:
    if tipo == "legitimo":
        return None
    clave = _clave(upz, tipo)
    if firebase_db.alerta_comunitaria_reciente(clave):
        return None

    recientes = [r for r in firebase_db.reportes_publicos_desde(settings.BROTE_VENTANA_HORAS)
                 if r.get("upz") == upz and r.get("tipo_fraude") == tipo and r.get("nivel_riesgo", 0) >= 40]
    if len(recientes) < settings.BROTE_MINIMO:
        return None

    nombre = nombre_tipo(tipo)
    texto = (f"🚨 *Alerta temprana · Escudo Comunitario*\n"
             f"En la UPZ {upz} se reportaron {len(recientes)} casos de {nombre.lower()} "
             f"en las últimas {settings.BROTE_VENTANA_HORAS} horas.\n"
             f"Avisa a tus vecinos: no compartan códigos ni consignen a cuentas desconocidas.\n"
             f"Panel: {settings.APP_URL}")
    alerta = {
        "upz": upz,
        "tipo_fraude": tipo,
        "nombre_tipo": nombre,
        "casos": len(recientes),
        "ventana_horas": settings.BROTE_VENTANA_HORAS,
        "mensaje": f"{len(recientes)} casos de {nombre.lower()} en {settings.BROTE_VENTANA_HORAS} h",
    }
    alerta["lideres_notificados"] = _avisar_lideres(texto)
    firebase_db.guardar_alerta_comunitaria(clave, alerta)
    return alerta
