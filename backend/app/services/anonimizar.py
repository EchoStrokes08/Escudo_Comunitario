"""
Anonimización para el panel público (Ley 1581 de 2012, habeas data).

  - El teléfono de quien reporta nunca se publica: se guarda un seudónimo
    sha256(sal + número) que permite contar reportes de la misma persona sin
    saber quién es.
  - El mensaje público oculta teléfonos, cédulas, correos, tarjetas y nombres
    propios precedidos de fórmulas típicas ("soy", "me llamo", "señora").
  - Los enlaces quedan "desactivados" (nequi-verificacion[.]top) para que nadie
    los abra desde el panel.
  - La ubicación se generaliza a una celda de ~220 m.
"""
import hashlib
import re

from app.core.config import settings
from app.services.geolocalizacion import dentro_de_bosa

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_TARJETA = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_TELEFONO = re.compile(r"(?:\+?57[\s-]?)?\b3\d{2}[\s-]?\d{3}[\s-]?\d{4}\b")
_CEDULA = re.compile(r"\b(c\.?\s?c\.?|c[eé]dula|documento|nit)\s*(n[oº°.]*\s*)?[:#]?\s*[\d.]{6,13}", re.IGNORECASE)
_NUMERO_LARGO = re.compile(r"\b\d{7,}\b")
_NOMBRE = re.compile(
    r"\b(soy|me llamo|mi nombre es|se[ñn]or(?:a|ita)?|sr\.?|sra\.?|don|doña|querid[oa])\s+"
    r"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,2})"
)
_URL = re.compile(r"((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*)\.([a-z]{2,})(\b)", re.IGNORECASE)

MAX_PUBLICO = 280
_CELDA = 0.002  # ~220 m en Bogotá


def seudonimo(identificador: str | None) -> str:
    """Huella irreversible del reportante (teléfono) para no guardar el número."""
    if not identificador:
        return "anonimo"
    limpio = re.sub(r"\D", "", identificador) or identificador
    return "rep-" + hashlib.sha256(f"{settings.SAL_SEUDONIMO}:{limpio}".encode()).hexdigest()[:24]


def enmascarar(valor: str) -> str:
    """3001234567 → 300•••••67 ; dominios se desactivan."""
    valor = str(valor)
    if "." in valor and not valor.replace(".", "").isdigit():
        return desactivar_enlaces(valor)
    digitos = re.sub(r"\D", "", valor)
    if len(digitos) < 6:
        return "•" * len(digitos)
    return f"{digitos[:3]}{'•' * (len(digitos) - 5)}{digitos[-2:]}"


def desactivar_enlaces(texto: str) -> str:
    texto = re.sub(r"https?://", "", texto, flags=re.IGNORECASE)
    return _URL.sub(lambda m: f"{m.group(1)}[.]{m.group(2)}", texto)


def anonimizar_texto(texto: str, limite: int = MAX_PUBLICO) -> str:
    """Versión publicable del mensaje sospechoso."""
    t = texto or ""
    t = _EMAIL.sub("[correo]", t)
    t = _CEDULA.sub("[documento]", t)
    t = _TARJETA.sub("[número de tarjeta]", t)
    t = _TELEFONO.sub(lambda m: enmascarar(m.group(0)), t)
    t = _NUMERO_LARGO.sub(lambda m: enmascarar(m.group(0)), t)
    t = _NOMBRE.sub(lambda m: f"{m.group(1)} [nombre]", t)
    t = desactivar_enlaces(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= limite else t[: limite - 1].rstrip() + "…"


def generalizar_ubicacion(lat: float | None, lng: float | None) -> tuple[float | None, float | None]:
    """Redondea a una celda de ~220 m (centro de la celda), siempre dentro de Bosa."""
    if lat is None or lng is None:
        return None, None
    glat = round(round(lat / _CELDA) * _CELDA, 4)
    glng = round(round(lng / _CELDA) * _CELDA, 4)
    if dentro_de_bosa(glat, glng):
        return glat, glng
    return round(lat, 3), round(lng, 3)
