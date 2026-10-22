"""
Registro trazable e inmutable: cadena de hashes + anclaje en Bitcoin.

Cada reporte produce un "bloque" con campos canónicos (sin datos personales):

    {v, altura, prev, fecha, canal, reportante, hash_mensaje, adjuntos, analisis}

  hash = SHA-256 del JSON canónico (claves ordenadas, sin espacios, UTF-8).

  - prev encadena cada bloque con el anterior: alterar o borrar un reporte
    rompe todos los siguientes y la auditoría lo detecta (verificar_cadena).
  - hash_mensaje es el SHA-256 del texto: la víctima puede probar que SU
    mensaje es el registrado sin que el texto se publique.
  - Cada hash se envía a varios calendarios públicos de OpenTimestamps, que
    lo agregan en una transacción de Bitcoin: un sello de tiempo externo que
    ni los administradores de la base de datos pueden falsificar. Horas
    después la prueba se completa (completar_anclaje) y se comprueba contra
    la raíz de Merkle real del bloque de Bitcoin. El archivo .ots se verifica
    en https://opentimestamps.org, con `ots verify` o con
    scripts/verificar_certificado.py, junto con el JSON canónico del bloque.

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
from datetime import datetime, timezone

from app.core.config import settings
from app.services import ots

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


# Exactamente los espacios que quita String.prototype.trim() en el navegador. str.strip() de
# Python quita además \x1c-\x1f y \x85, y no quita ﻿: con él, un mensaje que empezara o
# terminara con esos caracteres daría otra huella en /verificar ("¿Es este mi mensaje?").
_ESPACIOS_JS = ("\t\n\v\f\r           "
                "       　﻿")


def normalizar_mensaje(texto: str) -> str:
    """Misma normalización que el frontend (api.js sha256Texto): CRLF→LF y trim() de JavaScript."""
    return (texto or "").replace("\r\n", "\n").strip(_ESPACIOS_JS)


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
    Envía el hash a TODOS los calendarios públicos de OpenTimestamps en paralelo y combina
    sus respuestas en una sola prueba (si un calendario desaparece, los otros la sostienen).
    La prueba queda pendiente hasta que los calendarios la incluyan en Bitcoin (unas horas);
    completar_anclaje la termina después.
    """
    sello, aceptaron, errores = await ots.sellar(bytes.fromhex(hash_hex), settings.OTS_CALENDARIOS,
                                                 timeout or settings.OTS_TIMEOUT)
    if not sello:
        return {"estado": "sin_anclar", "errores": errores}
    return {
        "estado": "pendiente_bitcoin",
        "calendario": aceptaron[0],
        "calendarios": aceptaron,
        "fecha": ahora(),
        "prueba_b64": base64.b64encode(ots.escribir_sello(sello)).decode("ascii"),
    }


async def completar_anclaje(hash_hex: str, anclaje: dict, timeout: float | None = None) -> dict | None:
    """
    Pide a los calendarios la parte de la prueba que ya llegó a Bitcoin y la comprueba contra la
    raíz de Merkle real del bloque (exploradores públicos). Devuelve el anclaje actualizado, o None
    si sigue igual (todavía no hay bloque de Bitcoin).
    """
    timeout = timeout or settings.OTS_TIMEOUT
    digest = bytes.fromhex(hash_hex)
    sello = ots.leer_respuesta_calendario(base64.b64decode(anclaje["prueba_b64"]), digest)
    nuevas = await ots.completar(sello, timeout)
    if not ots.bitcoin(sello):
        return None
    confirmacion = await ots.verificar_bitcoin(sello, timeout)
    if not confirmacion or not confirmacion["valido"]:
        # Nunca debería pasar con calendarios honestos: se deja constancia y no se marca como confirmado
        return {**anclaje, "estado": "invalido", "bitcoin": confirmacion}
    return {
        **anclaje,
        "estado": "confirmado_bitcoin",
        "prueba_b64": base64.b64encode(ots.escribir_sello(sello)).decode("ascii") if nuevas else anclaje["prueba_b64"],
        "bitcoin": {k: confirmacion[k] for k in ("altura", "bloque_hash", "hora_bloque", "fuente")},
    }


def archivo_ots(hash_hex: str, prueba_b64: str) -> bytes:
    """Archivo .ots verificable en opentimestamps.org o con `ots verify` (junto con el JSON canónico)."""
    return _OTS_MAGIC + _OTS_VERSION + _OTS_OP_SHA256 + bytes.fromhex(hash_hex) + base64.b64decode(prueba_b64)


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
