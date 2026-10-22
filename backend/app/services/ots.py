"""
OpenTimestamps sin dependencias: leer, combinar, completar y verificar pruebas.

Una prueba OpenTimestamps es un árbol de operaciones que parte del hash del
bloque (el certificado). Cada rama aplica operaciones (append, prepend,
sha256…) y termina en una "atestación":

  - Pendiente: "el calendario X recibió este compromiso"; la transacción en
    Bitcoin todavía no existe (tarda unas horas).
  - Bitcoin: "este resultado es la raíz de Merkle del bloque N de Bitcoin".

Ciclo de vida de un sello:

  1. sellar      → se envía el hash a VARIOS calendarios públicos a la vez y
                   las respuestas se combinan en un solo árbol (si uno se cae,
                   la prueba sigue completa con los demás).
  2. completar   → horas después, se pide a cada calendario la parte que
                   faltaba (/timestamp/<compromiso>) y se injerta en el árbol.
  3. verificar   → se recorre el árbol desde el hash del bloque hasta la
                   atestación de Bitcoin y se compara con la raíz de Merkle
                   real del bloque, consultada en exploradores públicos.

El archivo .ots que se descarga es el mismo formato del cliente oficial
(`ots verify`) y de https://opentimestamps.org.
"""
import asyncio
import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.core.red import SSL

log = logging.getLogger("escudo.ots")

MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
VERSION = 1
OP_SHA256 = 0x08

TAG_PENDIENTE = bytes.fromhex("83dfe30d2ef90c8e")
TAG_BITCOIN = bytes.fromhex("0588960d73d71901")

_OPS_UNARIAS = {
    0x02: lambda m: hashlib.sha1(m).digest(),
    0x03: lambda m: hashlib.new("ripemd160", m).digest(),
    0x08: lambda m: hashlib.sha256(m).digest(),
    0xF2: lambda m: m[::-1],
    0xF3: lambda m: m.hex().encode(),
}
_OPS_BINARIAS = {
    0xF0: lambda m, a: m + a,  # append
    0xF1: lambda m, a: a + m,  # prepend
}
_NOMBRES_OPS = {0x02: "sha1", 0x03: "ripemd160", 0x08: "sha256",
                0xF0: "append", 0xF1: "prepend", 0xF2: "reverse", 0xF3: "hexlify"}

EXPLORADORES = ("https://blockstream.info/api", "https://mempool.space/api")
ACCEPT = {"Accept": "application/vnd.opentimestamps.v1", "User-Agent": "EscudoComunitario/2.0"}


class PruebaInvalida(ValueError):
    """El archivo o la respuesta del calendario no tiene el formato de OpenTimestamps."""


# --------------------------------------------------------------------------- #
# Árbol de la prueba
# --------------------------------------------------------------------------- #

class Sello:
    """Nodo del árbol: el mensaje en este punto, sus atestaciones y sus ramas (op → subárbol)."""

    def __init__(self, msg: bytes):
        self.msg = msg
        self.atestaciones: list[tuple[bytes, bytes]] = []  # (tag, payload crudo)
        self.ops: list[tuple[int, bytes, "Sello"]] = []    # (código, argumento, hijo)

    def fusionar(self, otro: "Sello"):
        """Une otro árbol que parte del mismo mensaje (respuestas de varios calendarios, upgrades)."""
        if otro.msg != self.msg:
            raise PruebaInvalida("Los árboles no parten del mismo mensaje")
        for a in otro.atestaciones:
            if a not in self.atestaciones:
                self.atestaciones.append(a)
        for codigo, arg, hijo in otro.ops:
            existente = next((h for c, a, h in self.ops if c == codigo and a == arg), None)
            if existente:
                existente.fusionar(hijo)
            else:
                self.ops.append((codigo, arg, hijo))

    def recorrer(self):
        """Todas las (mensaje, atestación, nodo) del árbol."""
        for a in self.atestaciones:
            yield self.msg, a, self
        for _, _, hijo in self.ops:
            yield from hijo.recorrer()


# --------------------------------------------------------------------------- #
# Serialización (formato binario de python-opentimestamps)
# --------------------------------------------------------------------------- #

class _Lector:
    def __init__(self, datos: bytes):
        self.datos, self.pos = datos, 0

    def bytes(self, n: int) -> bytes:
        if self.pos + n > len(self.datos):
            raise PruebaInvalida("Prueba truncada")
        trozo = self.datos[self.pos:self.pos + n]
        self.pos += n
        return trozo

    def varuint(self) -> int:
        valor, desplazamiento = 0, 0
        while True:
            b = self.bytes(1)[0]
            valor |= (b & 0x7F) << desplazamiento
            if not b & 0x80:
                return valor
            desplazamiento += 7
            if desplazamiento > 63:
                raise PruebaInvalida("Entero demasiado largo")

    def varbytes(self, maximo: int = 8192) -> bytes:
        n = self.varuint()
        if n > maximo:
            raise PruebaInvalida("Campo demasiado largo")
        return self.bytes(n)


def _varuint(n: int) -> bytes:
    salida = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        salida.append(b | (0x80 if n else 0))
        if not n:
            return bytes(salida)


def _varbytes(b: bytes) -> bytes:
    return _varuint(len(b)) + b


def aplicar(codigo: int, arg: bytes, msg: bytes) -> bytes:
    if codigo in _OPS_BINARIAS:
        return _OPS_BINARIAS[codigo](msg, arg)
    if codigo in _OPS_UNARIAS:
        return _OPS_UNARIAS[codigo](msg)
    raise PruebaInvalida(f"Operación desconocida 0x{codigo:02x}")


def leer_sello(lector: _Lector, msg: bytes, profundidad: int = 0) -> Sello:
    if profundidad > 256:
        raise PruebaInvalida("Árbol demasiado profundo")
    sello = Sello(msg)

    def rama(tag: int):
        if tag == 0x00:
            sello.atestaciones.append((lector.bytes(8), lector.varbytes()))
            return
        arg = lector.varbytes(4096) if tag in _OPS_BINARIAS else b""
        if tag not in _OPS_BINARIAS and tag not in _OPS_UNARIAS:
            raise PruebaInvalida(f"Operación desconocida 0x{tag:02x}")
        resultado = aplicar(tag, arg, msg)
        sello.ops.append((tag, arg, leer_sello(lector, resultado, profundidad + 1)))

    tag = lector.bytes(1)[0]
    while tag == 0xFF:
        rama(lector.bytes(1)[0])
        tag = lector.bytes(1)[0]
    rama(tag)
    return sello


def escribir_sello(sello: Sello) -> bytes:
    ramas = [b"\x00" + tag + _varbytes(payload) for tag, payload in sello.atestaciones]
    for codigo, arg, hijo in sello.ops:
        cabeza = bytes([codigo]) + (_varbytes(arg) if codigo in _OPS_BINARIAS else b"")
        ramas.append(cabeza + escribir_sello(hijo))
    if not ramas:
        raise PruebaInvalida("Nodo sin atestaciones ni operaciones")
    return b"".join(b"\xff" + r for r in ramas[:-1]) + ramas[-1]


def leer_respuesta_calendario(datos: bytes, msg: bytes) -> Sello:
    """Lo que devuelven /digest y /timestamp/<compromiso>: un árbol que parte de msg."""
    lector = _Lector(datos)
    sello = leer_sello(lector, msg)
    if lector.pos != len(datos):
        raise PruebaInvalida("Datos sobrantes en la respuesta del calendario")
    return sello


def archivo(digest: bytes, sello: Sello) -> bytes:
    """Archivo .ots (DetachedTimestampFile) para un archivo cuyo SHA-256 es digest."""
    return MAGIC + _varuint(VERSION) + bytes([OP_SHA256]) + digest + escribir_sello(sello)


def leer_archivo(datos: bytes) -> tuple[bytes, Sello]:
    """Devuelve (digest del archivo, árbol). Solo acepta archivos con hash SHA-256."""
    lector = _Lector(datos)
    if lector.bytes(len(MAGIC)) != MAGIC:
        raise PruebaInvalida("No es un archivo .ots")
    if lector.varuint() != VERSION:
        raise PruebaInvalida("Versión de .ots no soportada")
    if lector.bytes(1)[0] != OP_SHA256:
        raise PruebaInvalida("Solo se admiten pruebas sobre SHA-256")
    digest = lector.bytes(32)
    sello = leer_sello(lector, digest)
    if lector.pos != len(datos):
        raise PruebaInvalida("Datos sobrantes en el .ots")
    return digest, sello


# --------------------------------------------------------------------------- #
# Atestaciones
# --------------------------------------------------------------------------- #

def calendario_de(payload: bytes) -> str:
    return _Lector(payload).varbytes(1000).decode("utf-8", "replace")


def altura_de(payload: bytes) -> int:
    return _Lector(payload).varuint()


def pendientes(sello: Sello) -> list[tuple[bytes, str, Sello]]:
    return [(msg, calendario_de(p), nodo) for msg, (tag, p), nodo in sello.recorrer() if tag == TAG_PENDIENTE]


def bitcoin(sello: Sello) -> list[tuple[bytes, int]]:
    """[(raíz de Merkle esperada, altura del bloque)] de las ramas ya confirmadas en Bitcoin."""
    return [(msg, altura_de(p)) for msg, (tag, p), _ in sello.recorrer() if tag == TAG_BITCOIN]


def describir(sello: Sello, sangria: str = "") -> str:
    """Árbol legible (como `ots info`), para el script de verificación."""
    lineas = []
    for tag, p in sello.atestaciones:
        if tag == TAG_PENDIENTE:
            lineas.append(f"{sangria}pendiente en {calendario_de(p)}")
        elif tag == TAG_BITCOIN:
            lineas.append(f"{sangria}BITCOIN bloque {altura_de(p)} (raíz de Merkle {sello.msg[::-1].hex()})")
        else:
            lineas.append(f"{sangria}atestación desconocida {tag.hex()}")
    for i, (codigo, arg, hijo) in enumerate(sello.ops):
        varias = len(sello.ops) + len(sello.atestaciones) > 1
        lineas.append(f"{sangria}{' -> ' if varias else ''}{_NOMBRES_OPS[codigo]} {arg.hex()}".rstrip())
        lineas.append(describir(hijo, sangria + ("    " if varias else "")))
    return "\n".join(l for l in lineas if l)


# --------------------------------------------------------------------------- #
# Red: calendarios y exploradores de Bitcoin
# --------------------------------------------------------------------------- #

async def sellar(digest: bytes, calendarios: list[str], timeout: float) -> tuple[Sello | None, list[str], list[str]]:
    """Envía el digest a todos los calendarios en paralelo. Devuelve (árbol combinado, aceptaron, errores)."""
    async def enviar(client: httpx.AsyncClient, calendario: str):
        resp = await client.post(f"{calendario.rstrip('/')}/digest", content=digest, headers=ACCEPT)
        resp.raise_for_status()
        return leer_respuesta_calendario(resp.content, digest)

    async with httpx.AsyncClient(verify=SSL, timeout=timeout) as client:
        respuestas = await asyncio.gather(*[enviar(client, c) for c in calendarios], return_exceptions=True)
    sello, aceptaron, errores = Sello(digest), [], []
    for calendario, r in zip(calendarios, respuestas):
        if isinstance(r, Exception):
            errores.append(f"{calendario}: {type(r).__name__}")
        else:
            sello.fusionar(r)
            aceptaron.append(calendario)
    return (sello if aceptaron else None), aceptaron, errores


async def completar(sello: Sello, timeout: float) -> int:
    """
    Pide a cada calendario la parte de la prueba que ya llegó a Bitcoin y la injerta en el árbol.
    Devuelve cuántas ramas pendientes se completaron (0 = todavía esperando el bloque).
    """
    async def pedir(client: httpx.AsyncClient, msg: bytes, calendario: str):
        resp = await client.get(f"{calendario.rstrip('/')}/timestamp/{msg.hex()}", headers=ACCEPT)
        if resp.status_code == 404:
            return None  # "Pending confirmation in Bitcoin blockchain"
        resp.raise_for_status()
        return leer_respuesta_calendario(resp.content, msg)

    faltan = [(msg, cal, nodo) for msg, cal, nodo in pendientes(sello) if not bitcoin(nodo)]
    if not faltan:
        return 0
    async with httpx.AsyncClient(verify=SSL, timeout=timeout) as client:
        respuestas = await asyncio.gather(*[pedir(client, m, c) for m, c, _ in faltan], return_exceptions=True)
    completadas = 0
    for (msg, calendario, nodo), r in zip(faltan, respuestas):
        if isinstance(r, Exception):
            log.warning("No se pudo completar el sello en %s: %s", calendario, r)
        elif r is not None and bitcoin(r):
            nodo.fusionar(r)
            completadas += 1
    return completadas


async def bloque_bitcoin(altura: int, timeout: float) -> dict:
    """Raíz de Merkle y hora de un bloque de Bitcoin, consultadas en dos exploradores independientes."""
    errores = []
    async with httpx.AsyncClient(verify=SSL, timeout=timeout) as client:
        for base in EXPLORADORES:
            try:
                r = await client.get(f"{base}/block-height/{altura}")
                r.raise_for_status()
                bloque = (await client.get(f"{base}/block/{r.text.strip()}")).raise_for_status().json()
                return {"hash": bloque["id"], "merkle_root": bloque["merkle_root"],
                        "hora": bloque["timestamp"], "fuente": base}
            except Exception as error:
                errores.append(f"{base}: {type(error).__name__}")
    raise ConnectionError("; ".join(errores))


async def verificar_bitcoin(sello: Sello, timeout: float) -> dict | None:
    """
    Comprueba la primera rama confirmada contra la raíz de Merkle REAL del bloque de Bitcoin.
    None si la prueba aún no tiene ninguna rama en Bitcoin.
    """
    for msg, altura in sorted(bitcoin(sello), key=lambda x: x[1]):
        bloque = await bloque_bitcoin(altura, timeout)
        # Los exploradores muestran la raíz de Merkle con los bytes invertidos (orden de visualización)
        valido = msg[::-1].hex() == bloque["merkle_root"]
        return {
            "valido": valido,
            "altura": altura,
            "bloque_hash": bloque["hash"],
            "hora_bloque": datetime.fromtimestamp(bloque["hora"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fuente": bloque["fuente"],
        }
    return None
