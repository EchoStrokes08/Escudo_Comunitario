"""
Verificación en fuentes abiertas, en tiempo real.

Extrae URLs, dominios, teléfonos y números de cuenta (del texto, del OCR de
las capturas y de la transcripción de audio) y los contrasta en paralelo con:

  1. RDAP (registro público de dominios, sin clave): antigüedad del dominio.
     Un dominio creado hace días que se hace pasar por un banco es una señal fuerte.
  2. Detección de suplantación de marca: dominios que contienen o imitan
     (typosquatting) a Nequi, Bancolombia, DIAN... sin ser el dominio oficial.
  3. Expansión de enlaces acortados (bit.ly, tinyurl…) para revelar el destino.
  4. OpenPhish (feed público de sitios de phishing activos, sin clave), URLhaus
     (abuse.ch) y Google Safe Browsing (estas dos si hay clave configurada).
  5. Historial comunitario: cuántas veces otros vecinos ya reportaron ese
     mismo dominio, cuenta o teléfono (services.firebase_db.consultar_indicadores).
  6. Lista de referencia local (datos de demostración, marcados como tales).

Cada fuente informa su estado ("consultada", "sin datos", "no configurada",
"error") para que la verificación sea transparente.
"""
import asyncio
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.core.config import settings

# --------------------------------------------------------------------------- #
# Datos de referencia
# --------------------------------------------------------------------------- #

FUENTE_DEMO = "Lista de referencia Escudo Comunitario (datos de demostración)"

DOMINIOS_REFERENCIA: dict[str, str] = {
    "bosa-seguro-login.co": "Phishing bancario",
    "premios-bogota.top": "Sorteo falso",
    "nequi-verificacion-cliente.com": "Suplantación de Nequi",
    "bancolombia-soporte-clientes.xyz": "Phishing bancario",
    "cajero-virtual-bosa.info": "Robo de credenciales",
    "actualiza-datos-daviplata.site": "Suplantación de Daviplata",
    "pagos-bosa.gob-verificacion.net": "Suplantación de entidad pública",
}

CUENTAS_REFERENCIA: dict[str, dict] = {
    "3001234567": {"tipo": "Cuenta Nequi", "reporte": "Venta de celulares falsos en Bosa"},
    "3019876543": {"tipo": "Cuenta Bancolombia", "reporte": "Extorsión con supuesto secuestro de familiar"},
    "1555123456789012": {"tipo": "Cuenta Nequi", "reporte": "Premio falso de lotería Bogotá"},
}

# Marca → dominios oficiales. Un dominio que nombra la marca y no termina en uno de estos es sospechoso.
MARCAS_OFICIALES: dict[str, tuple[str, ...]] = {
    "nequi": ("nequi.com.co",),
    "bancolombia": ("bancolombia.com", "bancolombia.com.co", "grupobancolombia.com"),
    "daviplata": ("daviplata.com",),
    "davivienda": ("davivienda.com",),
    "bbva": ("bbva.com.co", "bbva.com"),
    "bancodebogota": ("bancodebogota.com", "bancodebogota.com.co"),
    "colpatria": ("scotiabankcolpatria.com",),
    "movii": ("movii.com.co",),
    "dian": ("dian.gov.co",),
    "policia": ("policia.gov.co",),
    "fiscalia": ("fiscalia.gov.co",),
    "sisben": ("sisben.gov.co",),
    "registraduria": ("registraduria.gov.co",),
    "simit": ("fcm.org.co", "simit.org.co"),
    "claro": ("claro.com.co",),
    "movistar": ("movistar.co",),
    "tigo": ("tigo.com.co",),
    "whatsapp": ("whatsapp.com", "wa.me"),
}

ACORTADORES = {
    "bit.ly", "tinyurl.com", "cutt.ly", "t.co", "is.gd", "rb.gy", "shorturl.at",
    "acortar.link", "ow.ly", "tiny.cc", "s.id", "rebrand.ly", "t.ly", "shorturl.gg",
}

# TLD de dos niveles frecuentes en Colombia (para obtener el dominio registrable)
_SEGUNDO_NIVEL = {"com.co", "gov.co", "net.co", "org.co", "edu.co", "mil.co", "nom.co", "co.uk", "com.br", "com.mx"}

_URL_REGEX = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+|\b[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.[a-z]{2,}(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)
_TLD_VALIDOS_EXTRA = re.compile(r"\.(com|co|net|org|gov|info|top|xyz|site|online|click|link|ly|me|io|app|shop|store|live|vip|lat|cc|us|gd|at|gg|id)$")

# Patrones de identificadores de cuenta en Colombia
_PATRONES_CUENTA = [
    ("Nequi", re.compile(r"nequi[^\d]{0,15}(3\d{9})")),
    ("Daviplata", re.compile(r"daviplata[^\d]{0,15}(3\d{9})")),
    ("Cuenta bancaria", re.compile(r"(?:cuenta|ahorros|corriente|consign\w*)[^\d]{0,25}(\d{8,20})")),
]
_TELEFONO_REGEX = re.compile(r"(?:\+?57[\s-]?)?\b(3\d{2})[\s-]?(\d{3})[\s-]?(\d{4})\b")


# --------------------------------------------------------------------------- #
# Extracción
# --------------------------------------------------------------------------- #

_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def es_ip(host: str) -> bool:
    return bool(_IPV4.match(host or ""))


def dominio_registrable(host: str) -> str:
    if es_ip(host):
        return host
    partes = host.lower().strip(".").split(".")
    if len(partes) >= 3 and ".".join(partes[-2:]) in _SEGUNDO_NIVEL:
        return ".".join(partes[-3:])
    return ".".join(partes[-2:])


def extraer_urls(texto: str) -> list[str]:
    urls = []
    for candidato in _URL_REGEX.findall(texto or ""):
        candidato = candidato.rstrip(".,;:!?)»”'\"")
        host = urlparse(candidato if "://" in candidato else f"http://{candidato}").hostname or ""
        # Evita falsos positivos tipo "hola.que" o números con punto
        if "://" in candidato or candidato.lower().startswith("www.") or _TLD_VALIDOS_EXTRA.search(host):
            urls.append(candidato)
    return list(dict.fromkeys(urls))


def host_de(url: str) -> str:
    host = urlparse(url if "://" in url else f"http://{url}").hostname or ""
    return host.lower().removeprefix("www.")


def extraer_dominios(texto: str) -> list[str]:
    return list(dict.fromkeys(h for h in (host_de(u) for u in extraer_urls(texto)) if "." in h))


def extraer_cuentas(texto: str) -> list[dict]:
    cuentas, vistos = [], set()
    texto_lower = (texto or "").lower()
    for tipo, patron in _PATRONES_CUENTA:
        for match in patron.finditer(texto_lower):
            valor = match.group(1)
            if valor not in vistos:
                vistos.add(valor)
                cuentas.append({"tipo": tipo, "valor": valor})
    return cuentas


def extraer_telefonos(texto: str) -> list[str]:
    return list(dict.fromkeys("".join(m) for m in _TELEFONO_REGEX.findall(texto or "")))


# --------------------------------------------------------------------------- #
# Suplantación de marca (sin red)
# --------------------------------------------------------------------------- #

def _distancia(a: str, b: str) -> int:
    """Levenshtein (cadenas cortas)."""
    if abs(len(a) - len(b)) > 2:
        return 99
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def imita_marca(dominio: str) -> str | None:
    """Retorna la marca imitada si el dominio la nombra (o casi) sin ser el oficial."""
    dominio = dominio.lower()
    if any(dominio == o or dominio.endswith("." + o) for oficiales in MARCAS_OFICIALES.values() for o in oficiales):
        return None
    compacto = dominio.replace("-", "").replace(".", "")
    for marca in MARCAS_OFICIALES:
        if marca in compacto and len(marca) >= 4:
            return marca
    for trozo in re.split(r"[.\-]", dominio):
        for marca in MARCAS_OFICIALES:
            if len(marca) >= 5 and len(trozo) >= 5 and 0 < _distancia(trozo, marca) <= 1:
                return marca
    return None


# --------------------------------------------------------------------------- #
# Fuentes en red (todas con timeout corto y sin romper el flujo)
# --------------------------------------------------------------------------- #

async def _rdap(client: httpx.AsyncClient, dominio: str) -> dict | None:
    """Fecha de registro del dominio vía RDAP (rdap.org redirige al registro de cada TLD)."""
    resp = await client.get(f"https://rdap.org/domain/{dominio}", follow_redirects=True,
                            headers={"Accept": "application/rdap+json"})
    if resp.status_code == 404:
        return {"existe": False}
    resp.raise_for_status()
    for evento in resp.json().get("events", []):
        if evento.get("eventAction") == "registration" and evento.get("eventDate"):
            creado = datetime.fromisoformat(evento["eventDate"].replace("Z", "+00:00"))
            return {"existe": True, "creado": creado.date().isoformat(),
                    "dias": (datetime.now(timezone.utc) - creado).days}
    return {"existe": True}


async def _expandir(client: httpx.AsyncClient, url: str) -> str | None:
    """Sigue hasta 3 redirecciones de un acortador sin visitar el destino final."""
    actual = url if "://" in url else f"https://{url}"
    for _ in range(3):
        if host_de(actual) not in ACORTADORES:
            return actual
        resp = await client.head(actual, follow_redirects=False)
        destino = resp.headers.get("location")
        if not destino:
            return None
        actual = destino if "://" in destino else f"https://{host_de(actual)}{destino}"
    return actual


async def _urlhaus(client: httpx.AsyncClient, dominio: str) -> dict | None:
    resp = await client.post("https://urlhaus-api.abuse.ch/v1/host/", data={"host": dominio},
                             headers={"Auth-Key": settings.URLHAUS_AUTH_KEY})
    resp.raise_for_status()
    data = resp.json()
    if data.get("query_status") == "ok":
        return {"urls": int(data.get("url_count") or 0)}
    return None


async def _safe_browsing(client: httpx.AsyncClient, urls: list[str]) -> set[str]:
    payload = {
        "client": {"clientId": "escudo-comunitario", "clientVersion": "2.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u if "://" in u else f"http://{u}"} for u in urls],
        },
    }
    resp = await client.post(
        f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={settings.GOOGLE_SAFE_BROWSING_KEY}",
        json=payload,
    )
    resp.raise_for_status()
    return {host_de(m["threat"]["url"]) for m in resp.json().get("matches", [])}


# Feed comunitario de OpenPhish (sitios de phishing activos, gratuito y sin clave), en caché 1 h
OPENPHISH_FEED = "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt"
_openphish: dict = {"hosts": set(), "cargado": 0.0}


async def _hosts_openphish(client: httpx.AsyncClient) -> set[str]:
    if time.monotonic() - _openphish["cargado"] < 3600 and _openphish["hosts"]:
        return _openphish["hosts"]
    resp = await client.get(OPENPHISH_FEED, follow_redirects=True)
    resp.raise_for_status()
    hosts = {host_de(linea.strip()) for linea in resp.text.splitlines() if linea.strip()}
    _openphish.update(hosts={h for h in hosts if h}, cargado=time.monotonic())
    return _openphish["hosts"]


async def _seguro(coro):
    """Ejecuta una consulta externa; cualquier error se reporta, no se propaga."""
    try:
        return await coro, None
    except Exception as error:  # timeout, DNS, HTTP…
        return None, type(error).__name__


# --------------------------------------------------------------------------- #
# Verificación principal
# --------------------------------------------------------------------------- #

def _indicadores(texto: str, extra: dict | None) -> tuple[list[str], list[str], list[dict], list[str]]:
    """URLs, dominios, cuentas y teléfonos del texto + los que el LLM leyó en los adjuntos."""
    extra = extra or {}
    urls = extraer_urls(texto)
    for u in extra.get("urls", []):
        urls.extend(extraer_urls(u) or [])
    urls = list(dict.fromkeys(urls))[:10]
    dominios = list(dict.fromkeys(h for h in (host_de(u) for u in urls) if "." in h))

    cuentas = extraer_cuentas(texto)
    vistos = {c["valor"] for c in cuentas}
    for c in extra.get("cuentas", []):
        if c and len(c) >= 8 and c not in vistos:
            vistos.add(c)
            cuentas.append({"tipo": "Cuenta (leída en adjunto)", "valor": c})

    telefonos = extraer_telefonos(texto)
    for t in extra.get("telefonos", []):
        t = t[-10:]
        if re.fullmatch(r"3\d{9}", t) and t not in telefonos:
            telefonos.append(t)
    # Un número Nequi/Daviplata ya es cuenta: no duplicarlo como teléfono
    telefonos = [t for t in telefonos if t not in vistos][:10]
    return urls, dominios, cuentas[:10], telefonos


def claves_indicadores(texto: str, indicadores_extra: dict | None = None) -> list[tuple[str, str]]:
    """(tipo, valor) de los dominios, cuentas y teléfonos, sin consultar la red."""
    _urls, dominios, cuentas, telefonos = _indicadores(texto, indicadores_extra)
    return [("dominio", dominio_registrable(d)) for d in dominios] + \
           [("cuenta", c["valor"]) for c in cuentas] + [("telefono", t) for t in telefonos]


async def verificar_mensaje(texto: str, indicadores_extra: dict | None = None,
                            historial=None, timeout_red: float | None = None) -> dict:
    """
    Cruza los elementos del mensaje contra las fuentes abiertas.
    historial: función opcional (lista de (tipo, valor)) → {clave: veces} con los
    reportes comunitarios previos (services.firebase_db.consultar_indicadores).
    """
    urls, dominios, cuentas, telefonos = _indicadores(texto, indicadores_extra)
    hallazgos: list[dict] = []
    fuentes: dict[str, str] = {}
    segundos = timeout_red or settings.VERIFICACION_TIMEOUT
    timeout = httpx.Timeout(segundos, connect=min(3.0, segundos))

    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "EscudoComunitario/2.0"}) as client:
        # 1. Acortadores → destino real (se agrega a los dominios a revisar)
        acortados = [u for u in urls if host_de(u) in ACORTADORES]
        if acortados:
            expandidos = await asyncio.gather(*[_seguro(_expandir(client, u)) for u in acortados])
            fuentes["Expansión de enlaces acortados"] = "consultada"
            for url, (destino, _err) in zip(acortados, expandidos):
                if destino and host_de(destino) not in ACORTADORES:
                    hallazgos.append({"tipo": "enlace", "valor": host_de(url),
                                      "detalle": f"Enlace acortado que redirige a {host_de(destino)}",
                                      "fuente": "Expansión de enlaces acortados", "gravedad": 10})
                    if host_de(destino) not in dominios:
                        dominios.append(host_de(destino))

        registrables = list(dict.fromkeys(dominio_registrable(d) for d in dominios
                                          if host_de(d) not in ACORTADORES))[:6]

        # 2. Consultas en paralelo: RDAP, URLhaus, Safe Browsing
        con_dominio = [d for d in registrables if not es_ip(d)]  # RDAP de dominios no aplica a IPs
        tareas_rdap = [_seguro(_rdap(client, d)) for d in con_dominio]
        tareas_urlhaus = [_seguro(_urlhaus(client, d)) for d in registrables] if settings.URLHAUS_AUTH_KEY else []
        tarea_sb = [_seguro(_safe_browsing(client, urls + registrables))] \
            if settings.GOOGLE_SAFE_BROWSING_KEY and (urls or registrables) else []
        tarea_op = [_seguro(_hosts_openphish(client))] if dominios else []
        resultados = await asyncio.gather(*tareas_rdap, *tareas_urlhaus, *tarea_sb, *tarea_op)

    res_rdap = resultados[:len(tareas_rdap)]
    res_urlhaus = resultados[len(tareas_rdap):len(tareas_rdap) + len(tareas_urlhaus)]
    res_sb = resultados[len(tareas_rdap) + len(tareas_urlhaus):len(tareas_rdap) + len(tareas_urlhaus) + len(tarea_sb)]
    res_op = resultados[len(resultados) - len(tarea_op):] if tarea_op else []

    if registrables:
        if con_dominio:
            errores_rdap = sum(1 for _r, e in res_rdap if e)
            fuentes["RDAP · registro público de dominios"] = "error" if errores_rdap == len(con_dominio) else "consultada"
        fuentes["URLhaus (abuse.ch)"] = "consultada" if tareas_urlhaus else "no configurada"
        fuentes["Google Safe Browsing"] = "consultada" if tarea_sb else "no configurada"
    if res_op:
        hosts_phishing, error_op = res_op[0]
        fuentes["OpenPhish · sitios de phishing reportados"] = "error" if error_op else "consultada"
        for dominio in dominios:
            # Coincidencia exacta de host: en hostings compartidos (pages.dev, vercel.app) no se marca a todos
            if hosts_phishing and dominio in hosts_phishing:
                hallazgos.append({"tipo": "dominio", "valor": dominio, "detalle": "Reportado como sitio de phishing activo",
                                  "fuente": "OpenPhish · sitios de phishing reportados", "gravedad": 35})

    for ip in [d for d in registrables if es_ip(d)]:
        hallazgos.append({"tipo": "dominio", "valor": ip,
                          "detalle": "El enlace apunta a una dirección IP en vez de un sitio con nombre (típico de malware)",
                          "fuente": "Análisis del enlace", "gravedad": 15})
    for dominio, (info, _err) in zip(con_dominio, res_rdap):
        if not info:
            continue
        if info.get("existe") is False:
            hallazgos.append({"tipo": "dominio", "valor": dominio, "detalle": "El dominio no está registrado (enlace falso o dado de baja)",
                              "fuente": "RDAP · registro público de dominios", "gravedad": 10})
        elif info.get("dias") is not None and info["dias"] <= 180:
            gravedad = 25 if info["dias"] <= 30 else 15
            hallazgos.append({"tipo": "dominio", "valor": dominio,
                              "detalle": f"Dominio creado hace solo {info['dias']} días ({info['creado']})",
                              "fuente": "RDAP · registro público de dominios", "gravedad": gravedad})

    for dominio, (info, _err) in zip(registrables, res_urlhaus):
        if info:
            hallazgos.append({"tipo": "dominio", "valor": dominio,
                              "detalle": f"Listado como malicioso en URLhaus ({info['urls']} URLs reportadas)",
                              "fuente": "URLhaus (abuse.ch)", "gravedad": 35})
    for detectados, _err in res_sb:
        for dominio in sorted(detectados or []):
            hallazgos.append({"tipo": "dominio", "valor": dominio, "detalle": "Marcado como peligroso por Google",
                              "fuente": "Google Safe Browsing", "gravedad": 35})

    # 3. Suplantación de marca
    if dominios:
        fuentes["Detección de suplantación de marca"] = "consultada"
    for dominio in dominios:
        marca = imita_marca(dominio)
        if marca:
            oficial = MARCAS_OFICIALES[marca][0]
            hallazgos.append({"tipo": "dominio", "valor": dominio,
                              "detalle": f"Imita a {marca.capitalize()} pero no es su dominio oficial ({oficial})",
                              "fuente": "Detección de suplantación de marca", "gravedad": 25})

    # 4. Lista de referencia (demostración)
    fuentes[FUENTE_DEMO] = "consultada"
    for dominio in dominios:
        for malicioso, categoria in DOMINIOS_REFERENCIA.items():
            if dominio == malicioso or dominio.endswith("." + malicioso):
                hallazgos.append({"tipo": "dominio", "valor": dominio, "detalle": categoria,
                                  "fuente": FUENTE_DEMO, "gravedad": 25, "simulada": True})
    for cuenta in cuentas:
        ref = CUENTAS_REFERENCIA.get(cuenta["valor"])
        if ref:
            hallazgos.append({"tipo": "cuenta", "valor": f"{ref['tipo']} {cuenta['valor']}", "detalle": ref["reporte"],
                              "fuente": FUENTE_DEMO, "gravedad": 25, "simulada": True})

    # 5. Historial comunitario (otros vecinos ya lo reportaron)
    claves = [("dominio", dominio_registrable(d)) for d in dominios] + \
             [("cuenta", c["valor"]) for c in cuentas] + [("telefono", t) for t in telefonos]
    comunidad = []
    if historial and claves:
        try:
            veces = historial(claves)
            fuentes["Reportes de la comunidad de Bosa"] = "consultada"
        except Exception:
            veces = {}
            fuentes["Reportes de la comunidad de Bosa"] = "error"
        for tipo, valor in claves:
            n = veces.get((tipo, valor), 0)
            if n > 0:
                comunidad.append({"tipo": tipo, "valor": valor, "veces": n})
                hallazgos.append({"tipo": tipo, "valor": valor,
                                  "detalle": f"Ya fue reportado {n} {'vez' if n == 1 else 'veces'} por vecinos de Bosa",
                                  "fuente": "Reportes de la comunidad de Bosa",
                                  "gravedad": 25 if n >= 3 else 15})

    reales = [h for h in hallazgos if not h.get("simulada")]
    return {
        "urls": urls,
        "dominios": dominios,
        "cuentas": cuentas,
        "telefonos": telefonos,
        "indicadores": claves,
        "hallazgos": hallazgos,
        "coincidencias": len(hallazgos),
        "coincidencias_reales": len(reales),
        "comunidad": comunidad,
        "arriesgado": any(h["gravedad"] >= 25 for h in hallazgos),
        "fuentes": [{"nombre": n, "estado": e} for n, e in fuentes.items()],
    }
