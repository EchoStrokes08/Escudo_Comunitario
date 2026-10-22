"""
Respuestas en audio para personas con baja alfabetización digital.

Quien manda una nota de voz probablemente prefiere ESCUCHAR la respuesta: el
bot le devuelve el veredicto hablado (MP3) en Telegram y WhatsApp, y la web
lo reproduce desde GET /api/voz/{certificado}.mp3.

La síntesis usa el servicio de voz de Google Translate (gratuito y sin clave,
pero no oficial: si falla, el bot sigue respondiendo solo con texto). Solo se
sintetiza la versión PÚBLICA del caso (anonimizada), nunca el mensaje original.
"""
import asyncio
import logging
import re

import httpx

from app.core.config import settings
from app.core.red import SSL
from app.core.riesgo import nivel as nivel_riesgo
from app.services.orientacion import nombre_tipo, plan_accion

log = logging.getLogger("escudo.voz")

_URL_TTS = "https://translate.google.{tld}/translate_tts"
_MAX_TROZO = 190  # el servicio corta textos más largos


def texto_de_caso(publico: dict) -> str:
    """Guion hablado, corto y sencillo, a partir de la versión pública del caso."""
    riesgo = int(publico.get("nivel_riesgo", 0))
    nivel = nivel_riesgo(riesgo)
    tipo = publico.get("tipo_fraude", "otro")
    partes = {
        "alto": [f"Cuidado. Este mensaje es muy probablemente un fraude. Riesgo de {riesgo} por ciento."],
        "medio": [f"Atención. Este mensaje tiene señales de fraude. Riesgo de {riesgo} por ciento."],
        "bajo": [f"Riesgo bajo, de {riesgo} por ciento. No vemos señales claras de fraude, pero mantén la precaución."],
    }[nivel]
    if nivel != "bajo":
        partes.append(f"Parece un caso de {nombre_tipo(tipo).lower()}.")
    if publico.get("resumen"):
        partes.append(_hablable(publico["resumen"]) + ".")
    pasos = plan_accion(tipo, riesgo)[:3]
    if pasos:
        partes.append("Qué hacer ahora.")
        partes += [f"{n}. {_hablable(p['titulo'])}." for n, p in zip(("Uno", "Dos", "Tres"), pasos)]
    partes.append("Tu reporte quedó registrado con un certificado. Gracias por proteger a tu comunidad.")
    return " ".join(partes)


def _hablable(texto: str) -> str:
    """Quita emojis, asteriscos, enlaces desactivados y números enmascarados que suenan mal."""
    t = re.sub(r"(un |el )?(enlace|link|sitio|página|dominio)?( falso)?\s*\S+\[\.\]\S+", "un enlace falso", texto)
    t = re.sub(r"\d*•+\d*", "un número", t)
    t = re.sub(r"[*_~`#>|]", "", t)
    t = re.sub(r"[^\w\s.,;:¿?¡!%()áéíóúüñÁÉÍÓÚÜÑ-]", "", t)
    return re.sub(r"\s+", " ", t).strip().rstrip(".")


def _trozos(texto: str) -> list[str]:
    """Corta en frases (y, si hace falta, en comas o espacios) de máximo _MAX_TROZO caracteres."""
    trozos, actual = [], ""
    for frase in re.split(r"(?<=[.!?;:])\s+", texto):
        while len(frase) > _MAX_TROZO:
            corte = max(frase.rfind(",", 0, _MAX_TROZO), frase.rfind(" ", 0, _MAX_TROZO))
            corte = corte if corte > 40 else _MAX_TROZO
            trozos.append(frase[:corte + 1].strip())
            frase = frase[corte + 1:].strip()
        if len(actual) + len(frase) + 1 > _MAX_TROZO:
            trozos.append(actual)
            actual = frase
        else:
            actual = f"{actual} {frase}".strip()
    if actual:
        trozos.append(actual)
    return [t for t in trozos if t]


async def sintetizar(texto: str, timeout: float | None = None) -> bytes | None:
    """Texto → MP3 (los trozos MP3 se concatenan sin reprocesar). None si no se pudo."""
    if not settings.VOZ_RESPUESTAS or not texto.strip():
        return None
    trozos = _trozos(texto)[:12]
    url = _URL_TTS.format(tld=settings.VOZ_TLD)

    async def _uno(client: httpx.AsyncClient, i: int, trozo: str) -> bytes:
        resp = await client.get(url, params={
            "ie": "UTF-8", "q": trozo, "tl": "es", "client": "tw-ob", "total": len(trozos), "idx": i,
            "textlen": len(trozo), "ttsspeed": "0.9",  # un poco más lento: más fácil de entender
        }, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://translate.google.com/"})
        resp.raise_for_status()
        if not resp.headers.get("content-type", "").startswith("audio/"):
            raise ValueError("respuesta sin audio")
        return resp.content

    try:
        async with httpx.AsyncClient(verify=SSL, timeout=timeout or settings.VOZ_TIMEOUT) as client:
            partes = await asyncio.gather(*(_uno(client, i, t) for i, t in enumerate(trozos)))
        return b"".join(partes)
    except Exception as error:
        log.warning("No se pudo sintetizar la voz: %s", type(error).__name__)
        return None


async def audio_de_caso(publico: dict, timeout: float | None = None) -> bytes | None:
    return await sintetizar(texto_de_caso(publico), timeout=timeout)
