"""
Ubicación geográfica por UPZ (Unidades de Planeamiento Zonal) de Bosa (Bogotá).

Regla dura: TODO punto generado debe caer estrictamente dentro del polígono
oficial de Bosa (app.data.bosa_polygon).

Las 5 UPZ oficiales de la Localidad de Bosa son:
  - Apogeo (UPZ 49)
  - Bosa Occidental (UPZ 84)
  - Bosa Central (UPZ 85)
  - El Porvenir (UPZ 86)
  - Tintal Sur (UPZ 87)

Si el dispositivo del usuario envía su ubicación GPS precisa:
  - Solo se acepta si está estrictamente DENTRO de Bosa.
  - Si el usuario está en otra localidad o fuera de Bosa, se descarta el GPS
    para proteger la exactitud del mapa de calor y se georreferencia
    usando la UPZ seleccionada (con dispersión controlada dentro de la UPZ).
"""
import hashlib

from app.data.bosa_polygon import VERTICES_BOSA, dentro_de_bosa

# Centros geográficos de las 5 Unidades de Planeamiento Zonal (UPZ) de Bosa
UPZ_BOSA: dict[str, tuple[float, float]] = {
    "Apogeo": (4.6010, -74.1640),
    "Bosa Occidental": (4.6220, -74.2120),
    "Bosa Central": (4.6060, -74.1860),
    "El Porvenir": (4.6370, -74.2060),
    "Tintal Sur": (4.6240, -74.1900),
}

# Alias para compatibilidad con código o reportes previos
BARRIOS_BOSA = UPZ_BOSA

# Coordenadas de referencia central (Bosa Central / Alcaldía Local)
CENTRO_BOSA = UPZ_BOSA["Bosa Central"]

_RADIO_JITTER = 0.0035   # ~380 metros de dispersión máxima dentro de la UPZ
_INTENTOS_MAX = 20       # intentos de hallar un punto válido dentro del polígono


def _jitter(seed: str, eje: int) -> float:
    """Desplazamiento determinístico basado en un hash (mismo origen = mismo punto)."""
    digest = hashlib.sha256(f"{seed}:{eje}".encode()).digest()
    fraccion = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF  # 0..1
    return (fraccion * 2 - 1) * _RADIO_JITTER


def obtener_coordenadas(upz: str | None, seed: str = "") -> tuple[float, float]:
    """
    Retorna coordenadas (lat, lng) garantizadas dentro del polígono de Bosa.
    Si la UPZ coincide con una de las 5 UPZ de Bosa, se toma su centro; de lo
    contrario se usa el centro de Bosa Central. Luego se aplica jitter controlado.
    """
    nombre = (upz or "").strip()
    clave = next((u for u in UPZ_BOSA if u.lower() == nombre.lower()), None)
    base = UPZ_BOSA.get(clave, CENTRO_BOSA)

    if dentro_de_bosa(*base):
        punto_base = base
    else:
        punto_base = CENTRO_BOSA

    if not seed:
        return punto_base

    for intento in range(_INTENTOS_MAX):
        cand_lat = punto_base[0] + _jitter(f"{seed}:{intento}", 0)
        cand_lng = punto_base[1] + _jitter(f"{seed}:{intento}", 1)
        if dentro_de_bosa(cand_lat, cand_lng):
            return (round(cand_lat, 6), round(cand_lng, 6))

    return punto_base


def validar_o_asignar(lat, lng, upz: str | None, seed: str) -> tuple[float, float]:
    """
    Si el cliente envía coordenadas (ubicación obtenida del dispositivo):
      1. Se comprueba si caen estrictamente dentro de la localidad de Bosa.
      2. Si están dentro de Bosa, se preserva la ubicación precisa del dispositivo.
      3. Si están en otra localidad o fuera de Bosa (o son nulas), se descartan
         para no desviar el mapa de calor comunitario y se georreferencia
         usando la UPZ seleccionada (o centro).
    """
    if lat is not None and lng is not None and dentro_de_bosa(lat, lng):
        return (round(float(lat), 6), round(float(lng), 6))
    return obtener_coordenadas(upz, seed=seed)


# Exporta para que los módulos consumidores validen sin importar app.data directamente
__all__ = ["UPZ_BOSA", "BARRIOS_BOSA", "CENTRO_BOSA", "obtener_coordenadas",
           "validar_o_asignar", "dentro_de_bosa", "VERTICES_BOSA"]
