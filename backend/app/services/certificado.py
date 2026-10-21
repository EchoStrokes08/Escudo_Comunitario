"""
Generación del certificado trazable e inmanipulable (hash SHA-256).
Cualquier cambio en el contenido del reporte produce un hash distinto,
lo que permite verificar la integridad del registro.
"""
import hashlib
from datetime import datetime, timezone


def generar_certificado(mensaje: str, nivel_riesgo: int, fecha: str | None = None) -> str:
    """Retorna el hash SHA-256 completo (64 caracteres hexadecimales)."""
    fecha = fecha or datetime.now(timezone.utc).isoformat()
    payload = f"{mensaje.strip()}|{nivel_riesgo}|{fecha}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def certificado_corto(certificado: str) -> str:
    """Versión legible (16 caracteres) para mostrar en mensajes cortos de WhatsApp."""
    return certificado[:16]


def verificar_integridad(mensaje: str, nivel_riesgo: int, fecha: str, certificado: str) -> bool:
    """Recalcula el hash y lo compara con el certificado almacenado."""
    return generar_certificado(mensaje, nivel_riesgo, fecha) == certificado
