"""
Registro trazable e inmutable: cadena de hashes + anclaje en Bitcoin.

Cada reporte produce un "bloque" con campos canónicos (sin datos personales):

    {v, altura, prev, fecha, canal, reportante, hash_mensaje, adjuntos, analisis}

  hash = SHA-256 del JSON canónico (claves ordenadas, sin espacios, UTF-8).

  - prev encadena cada bloque con el anterior: alterar o borrar un reporte
    rompe todos los siguientes y la auditoría lo detecta (verificar_cadena).
  - hash_mensaje es el SHA-256 del texto: la víctima puede probar que SU
    mensaje es el registrado sin que el texto se publique.
  - Cada hash se envía a calendarios públicos de OpenTimestamps, que lo
    agregan en una transacción de Bitcoin: un sello de tiempo externo que ni
    los administradores de la base de datos pueden falsificar. El archivo
    .ots resultante se verifica en https://opentimestamps.org junto con el
    JSON canónico del bloque.

El certificado de reporte ES el hash del bloque.

Seguimiento del caso: cada cambio de estado (en revisión, remitido a la
Policía/Fiscalía, cerrado) es OTRO bloque de la misma cadena, de tipo
"seguimiento", que apunta al certificado del reporte:

    {v, tipo, altura, prev, fecha, caso, estado, actor, hash_nota}

Así la trazabilidad cubre todo el ciclo del caso: nadie puede cambiar a
escondidas cuándo se remitió un caso ni qué se le respondió a la víctima.
"""
import base64
import hashlib
import json

import httpx

from app.core.config import settings
from app.core.red import SSL

VERSION = 1
GENESIS = "0" * 64

# Formato de archivo .ots (DetachedTimestampFile de OpenTimestamps)
_OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
_OTS_VERSION = b"\x01"
_OTS_OP_SHA256 = b"\x08"

CAMPOS_BLOQUE = ("v", "altura", "prev", "fecha", "canal", "reportante", "hash_mensaje", "adjuntos", "analisis")
CAMPOS_SEGUIMIENTO = ("v", "tipo", "altura", "prev", "fecha", "caso", "estado", "actor", "hash_nota")

# Ciclo de vida de un caso. "registrado" es el estado implícito del bloque del reporte.
ESTADOS_CASO: dict[str, str] = {
    "registrado": "Reporte registrado",
    "en_revision": "En revisión",
    "remitido": "Remitido a Policía / Fiscalía",
    "en_investigacion": "En investigación",
    "cerrado": "Caso cerrado",
}


def normalizar_mensaje(texto: str) -> str:
    """Misma normalización que el frontend (Verificar.jsx): CRLF→LF y sin espacios en los extremos."""
    return (texto or "").replace("\r\n", "\n").strip()


def hash_mensaje(texto: str) -> str:
    return hashlib.sha256(normalizar_mensaje(texto).encode("utf-8")).hexdigest()


def construir_bloque(*, altura: int, prev: str, fecha: str, canal: str, reportante: str,
                     mensaje: str, adjuntos: list[dict], analisis: dict) -> dict:
    return {
        "v": VERSION,
        "altura": altura,
        "prev": prev,
        "fecha": fecha,
        "canal": canal,
        "reportante": reportante,
        "hash_mensaje": hash_mensaje(mensaje),
        "adjuntos": sorted(a["sha256"] for a in adjuntos),
        "analisis": {
            "nivel_riesgo": int(analisis["nivel_riesgo"]),
            "confianza": int(analisis["confianza"]),
            "tipo_fraude": analisis["tipo_fraude"],
            "flags": list(analisis.get("flags", []))[:10],
            "motor": analisis.get("motor", ""),
        },
    }


def construir_seguimiento(*, altura: int, prev: str, fecha: str, caso: str, estado: str,
                          actor: str, nota: str) -> dict:
    return {
        "v": VERSION,
        "tipo": "seguimiento",
        "altura": altura,
        "prev": prev,
        "fecha": fecha,
        "caso": caso,
        "estado": estado,
        "actor": actor,
        # La nota se publica junto al bloque; su huella la protege de cambios posteriores
        "hash_nota": hash_mensaje(nota),
    }


def es_seguimiento(bloque: dict) -> bool:
    return bloque.get("tipo") == "seguimiento"


def canonico(bloque: dict) -> bytes:
    campos = CAMPOS_SEGUIMIENTO if es_seguimiento(bloque) else CAMPOS_BLOQUE
    datos = {k: bloque[k] for k in campos}
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_bloque(bloque: dict) -> str:
    return hashlib.sha256(canonico(bloque)).hexdigest()


def certificado_corto(certificado: str) -> str:
    """Versión legible (16 caracteres) para mensajes cortos de WhatsApp."""
    return certificado[:16]


def verificar_bloque(hash_esperado: str, bloque: dict) -> bool:
    try:
        return hash_bloque(bloque) == hash_esperado
    except (KeyError, TypeError, ValueError):
        return False


def verificar_cadena(bloques: list[dict]) -> dict:
    """
    Recorre los bloques ordenados por altura y recalcula cada hash y cada enlace.
    Retorna {total, integros, valida, errores:[{altura, hash, motivo}]}.
    """
    errores = []
    danados = set()
    anterior = None
    for bloque in bloques:
        h = bloque.get("hash", "")
        altura = bloque.get("altura")
        if anterior is None:
            if altura == 0 and bloque.get("prev") != GENESIS:
                errores.append({"altura": altura, "hash": h, "motivo": "El bloque génesis fue alterado"})
                danados.add(h)
        elif altura != anterior["altura"] + 1:
            errores.append({"altura": anterior["altura"] + 1, "hash": None,
                            "motivo": f"Faltan bloques entre la altura {anterior['altura']} y {altura} (registros borrados)"})
            danados.add(h)
        elif bloque.get("prev") != anterior.get("hash"):
            errores.append({"altura": altura, "hash": h,
                            "motivo": "Enlace roto: 'prev' no apunta al bloque anterior (el anterior fue alterado)"})
            danados.add(h)
        if not verificar_bloque(h, bloque):
            errores.append({"altura": altura, "hash": h,
                            "motivo": "El contenido fue modificado: el hash recalculado ya no coincide"})
            danados.add(h)
        anterior = bloque
    return {
        "total": len(bloques),
        "integros": len(bloques) - len(danados),
        "valida": not errores,
        "errores": errores[:50],
    }


# --------------------------------------------------------------------------- #
# OpenTimestamps
# --------------------------------------------------------------------------- #

async def anclar_opentimestamps(hash_hex: str, timeout: float | None = None) -> dict:
    """
    Envía el hash a un calendario público de OpenTimestamps. Devuelve la prueba
    parcial (pendiente de confirmación en Bitcoin, normalmente en pocas horas).
    """
    digest = bytes.fromhex(hash_hex)
    errores = []
    async with httpx.AsyncClient(verify=SSL, timeout=timeout or settings.OTS_TIMEOUT) as client:
        for calendario in settings.OTS_CALENDARIOS:
            try:
                resp = await client.post(
                    f"{calendario.rstrip('/')}/digest",
                    content=digest,
                    headers={"Accept": "application/vnd.opentimestamps.v1",
                             "User-Agent": "EscudoComunitario/2.0"},
                )
                resp.raise_for_status()
                return {
                    "estado": "pendiente_bitcoin",
                    "calendario": calendario,
                    "prueba_b64": base64.b64encode(resp.content).decode("ascii"),
                }
            except Exception as error:
                errores.append(f"{calendario}: {type(error).__name__}")
    return {"estado": "sin_anclar", "errores": errores}


def archivo_ots(hash_hex: str, prueba_b64: str) -> bytes:
    """Archivo .ots verificable en opentimestamps.org (junto con el JSON canónico)."""
    return _OTS_MAGIC + _OTS_VERSION + _OTS_OP_SHA256 + bytes.fromhex(hash_hex) + base64.b64decode(prueba_b64)
