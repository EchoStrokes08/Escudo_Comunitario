"""
Ubicación geográfica por barrio de la Localidad de Bosa (Bogotá).
Se usa para georreferenciar reportes sin coordenadas exactas (canal WhatsApp).
"""
import hashlib

# Coordenadas centro aproximadas de cada barrio de Bosa
BARRIOS_BOSA: dict[str, tuple[float, float]] = {
    "Bosa Centro": (4.6060, -74.1860),
    "Ciudad Hunza": (4.6230, -74.1830),
    "Tintalito": (4.6170, -74.1940),
    "Timiza": (4.5950, -74.1830),
    "Britalia": (4.5900, -74.1750),
    "Villas Birhana": (4.5870, -74.1950),
    "Quiasco": (4.6250, -74.1750),
    "Pablo VI": (4.6130, -74.1750),
    "Cipacá": (4.5930, -74.1700),
    "Almeria": (4.6170, -74.1700),
}

# Coordenadas del CAI Bosa (punto central de respaldo)
CENTRO_BOSA = BARRIOS_BOSA["Bosa Centro"]

_RADIO_JITTER = 0.0045  # ~500 metros de dispersión máxima


def _jitter(seed: str, eje: int) -> float:
    """Desplazamiento determinístico basado en un hash (mismo origen = mismo punto)."""
    digest = hashlib.sha256(f"{seed}:{eje}".encode()).digest()
    fraccion = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF  # 0..1
    return (fraccion * 2 - 1) * _RADIO_JITTER


def obtener_coordenadas(barrio: str | None, seed: str = "") -> tuple[float, float]:
    """Retorna coordenadas (lat, lng) para un barrio, con dispersión anti-aglomeración."""
    base = BARRIOS_BOSA.get((barrio or "").strip().title(), CENTRO_BOSA)
    if not seed:
        return base
    return (
        round(base[0] + _jitter(seed, 0), 6),
        round(base[1] + _jitter(seed, 1), 6),
    )
