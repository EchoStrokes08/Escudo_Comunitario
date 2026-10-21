"""
Umbrales únicos de riesgo y confianza.

Son los mismos que usa el frontend (frontend/src/utils/riesgo.js), el prompt del
agente y las respuestas de WhatsApp: un caso nunca se ve "medio" en un canal y
"bajo" en otro.
"""

UMBRAL_ALTO = 70
UMBRAL_MEDIO = 40

UMBRAL_CONFIANZA_ALTA = 75
UMBRAL_CONFIANZA_MEDIA = 50


def nivel(riesgo: int) -> str:
    """'alto' | 'medio' | 'bajo'"""
    if riesgo >= UMBRAL_ALTO:
        return "alto"
    if riesgo >= UMBRAL_MEDIO:
        return "medio"
    return "bajo"


def nivel_confianza(confianza: int) -> str:
    """'alta' | 'media' | 'baja'"""
    if confianza >= UMBRAL_CONFIANZA_ALTA:
        return "alta"
    if confianza >= UMBRAL_CONFIANZA_MEDIA:
        return "media"
    return "baja"
