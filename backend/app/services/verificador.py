"""
Verificación automatizada en fuentes abiertas.

Extrae URLs, dominios y números de cuenta del mensaje y los cruza contra:
  1. Una lista local (mock) de dominios maliciosos conocidos.
  2. Reportes simulados del CAI Virtual de la Policía Nacional.

En producción, esta capa se conecta a APIs reales (e.g. Google Safe Browsing,
URLhaus, OpenPhish o los boletines del CAI Virtual); aquí la simulamos con
datasets locales para mantener el hackathon sin claves externas.
"""
import re
from urllib.parse import urlparse

# --------------------------------------------------------------------------- #
# Bases de datos simuladas
# --------------------------------------------------------------------------- #

# Lista mock de dominios maliciosos reportados (equivale a Google Safe Browsing / OpenPhish)
DOMINIOS_MALICIOSOS_MOCK: dict[str, dict] = {
    "bosa-seguro-login.co": {
        "categoria": "Phishing bancario",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "premios-bogota.top": {
        "categoria": "Sorteo falso",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "nequi-verificacion-cliente.com": {
        "categoria": "Suplantación de Nequi",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "bancolombia-soporte-clientes.xyz": {
        "categoria": "Phishing bancario",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "cajero-virtual-bosa.info": {
        "categoria": "Robo de credenciales",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "actualiza-datos-daviplata.site": {
        "categoria": "Suplantación de Daviplata",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
    "pagos-bosa.gob-verificacion.net": {
        "categoria": "Suplantación de entidad pública",
        "fuente": "Lista local de dominios maliciosos (simulada)",
    },
}

# Reportes mock del CAI Virtual - Policía Nacional (boletines de fraude)
REPORTES_CAI_MOCK: dict[str, dict] = {
    "3001234567": {
        "tipo": "Cuenta Nequi",
        "reporte": "Fraude por venta de celulares falsos en Bosa",
        "cai": "CAI Virtual - Policía Nacional (informe simulado N.º 2026-0412)",
    },
    "3019876543": {
        "tipo": "Cuenta Bancolombia",
        "reporte": "Extorsión con supuesto secuestro de familiar",
        "cai": "CAI Virtual - Policía Nacional (informe simulado N.º 2026-0518)",
    },
    "1555123456789012": {
        "tipo": "Cuenta Nequi",
        "reporte": "Premio falso de lotería Bogotá",
        "cai": "CAI Virtual - Policía Nacional (informe simulado N.º 2026-0333)",
    },
}

# Patrones de identificadores de cuenta en Colombia
_PATRONES_CUENTA = [
    ("Nequi", re.compile(r"\b(?:nequi[:\s]*)?(3\d{9})\b")),
    ("Daviplata", re.compile(r"\b(?:daviplata[:\s]*)?(3\d{9})\b")),
    ("Bancolombia", re.compile(r"\b(?:cuenta\s*(?:bancolombia)?[:\s]*)?(\d{7,12})\b")),
]

_URL_REGEX = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|[a-z0-9][a-z0-9\-]*\.[a-z]{2,}(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)


# --------------------------------------------------------------------------- #
# Extracción
# --------------------------------------------------------------------------- #

def extraer_urls(texto: str) -> list[str]:
    return list(dict.fromkeys(_URL_REGEX.findall(texto or "")))


def extraer_dominios(texto: str) -> list[str]:
    """Normaliza cada URL/token a su dominio raíz (sin www, en minúsculas)."""
    dominios = []
    for url in extraer_urls(texto):
        candidato = url if "://" in url else f"http://{url}"
        host = urlparse(candidato).hostname or ""
        host = host.lower().removeprefix("www.")
        if "." in host:
            dominios.append(host)
    return list(dict.fromkeys(dominios))


def extraer_cuentas(texto: str) -> list[dict]:
    """Detecta números de cuenta/wallet mencionados en el mensaje."""
    cuentas: list[dict] = []
    vistos: set[str] = set()
    texto_lower = (texto or "").lower()
    for tipo, patron in _PATRONES_CUENTA:
        for match in patron.finditer(texto_lower):
            valor = match.group(1)
            if valor in vistos:
                continue
            # Evita confundir teléfonos con cuentas cuando el contexto no lo indica
            if tipo == "Bancolombia" and len(valor) == 10 and valor.startswith("3"):
                continue
            vistos.add(valor)
            cuentas.append({"tipo": tipo, "valor": valor})
    return cuentas


# --------------------------------------------------------------------------- #
# Cruce contra fuentes abiertas
# --------------------------------------------------------------------------- #

def verificar_mensaje(texto: str) -> dict:
    """
    Cruza los elementos extraídos del mensaje contra las fuentes abiertas
    (mock) y retorna un dict con los hallazgos.
    """
    dominios = extraer_dominios(texto)
    cuentas = extraer_cuentas(texto)
    hallazgos: list[dict] = []

    for dominio in dominios:
        # Coincidencia exacta o subdominio de un dominio malicioso conocido
        for malicioso, info in DOMINIOS_MALICIOSOS_MOCK.items():
            if dominio == malicioso or dominio.endswith("." + malicioso):
                hallazgos.append({
                    "tipo": "dominio",
                    "valor": dominio,
                    "detalle": info["categoria"],
                    "fuente": info["fuente"],
                })

    for cuenta in cuentas:
        reporte = REPORTES_CAI_MOCK.get(cuenta["valor"])
        if reporte:
            hallazgos.append({
                "tipo": "cuenta",
                "valor": f"{cuenta['tipo']} {cuenta['valor']}",
                "detalle": reporte["reporte"],
                "fuente": reporte["cai"],
            })

    return {
        "dominios": dominios,
        "cuentas": cuentas,
        "hallazgos": hallazgos,
        "coincidencias": len(hallazgos),
        "arriesgado": len(hallazgos) > 0,
        "fuente": "CAI Virtual - Policía Nacional / Listas de dominios maliciosos (datos simulados)",
    }


# Bonus de riesgo aplicado cuando el cruce encuentra coincidencias en fuentes abiertas
BONUS_POR_HALLAZGO = 20


def riesgo_verificado(verificacion: dict, nivel_riesgo: int) -> int:
    """Ajusta el nivel de riesgo del LLM con los hallazgos de fuentes abiertas."""
    bonus = verificacion.get("coincidencias", 0) * BONUS_POR_HALLAZGO
    return max(0, min(100, nivel_riesgo + bonus))
