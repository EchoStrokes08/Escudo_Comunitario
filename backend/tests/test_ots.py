"""
Pruebas del sello en Bitcoin (OpenTimestamps), sin red.

Datos en tests/datos/ots/:
  - hello-world.txt(.ots): ejemplo oficial del cliente de OpenTimestamps, confirmado en el
    bloque 358391 de Bitcoin (raíz de Merkle conocida).
  - pendiente.json(.ots): un registro real de la app recién sellado (aún sin Bitcoin).
"""
import asyncio
import base64
import hashlib
from pathlib import Path

import pytest

from app.services import ots, registro

DATOS = Path(__file__).parent / "datos" / "ots"
# Raíz de Merkle del bloque 358391 tal como la muestran los exploradores (bytes invertidos)
MERKLE_358391 = "8a1b66ecb7cbd07d8139a7e7d7f2c41aab1f5009b8364aaf61d03ad245e47e00"


def _leer(nombre: str) -> bytes:
    return (DATOS / nombre).read_bytes()


def _explorador(merkle_root: str):
    async def falso(altura, timeout):
        return {"hash": "00" * 32, "merkle_root": merkle_root, "hora": 1432827678, "fuente": "prueba"}
    return falso


def test_lee_y_reescribe_pruebas_byte_a_byte():
    for nombre in ("hello-world.txt", "pendiente.json"):
        datos = _leer(nombre + ".ots")
        digest, sello = ots.leer_archivo(datos)
        assert digest == hashlib.sha256(_leer(nombre)).digest()
        assert ots.archivo(digest, sello) == datos


def test_pendiente_apunta_al_calendario():
    digest, sello = ots.leer_archivo(_leer("pendiente.json.ots"))
    assert digest.hex() == hashlib.sha256(_leer("pendiente.json")).hexdigest()
    assert [c for _, c, _ in ots.pendientes(sello)] == ["https://alice.btc.calendar.opentimestamps.org"]
    assert ots.bitcoin(sello) == []


def test_prueba_oficial_llega_a_la_raiz_de_merkle_del_bloque():
    _, sello = ots.leer_archivo(_leer("hello-world.txt.ots"))
    [(raiz, altura)] = ots.bitcoin(sello)
    assert altura == 358391 and raiz[::-1].hex() == MERKLE_358391


def test_verificar_bitcoin_detecta_raiz_falsa(monkeypatch):
    _, sello = ots.leer_archivo(_leer("hello-world.txt.ots"))
    monkeypatch.setattr(ots, "bloque_bitcoin", _explorador(MERKLE_358391))
    assert asyncio.run(ots.verificar_bitcoin(sello, 1))["valido"] is True
    monkeypatch.setattr(ots, "bloque_bitcoin", _explorador("11" * 32))
    assert asyncio.run(ots.verificar_bitcoin(sello, 1))["valido"] is False


def test_fusionar_varios_calendarios_conserva_todas_las_ramas():
    digest = hashlib.sha256(b"bloque").digest()
    ramas = []
    for calendario in ("https://a.example", "https://b.example"):
        s = ots.Sello(digest)
        hijo = ots.Sello(digest + calendario.encode())
        hijo.atestaciones.append((ots.TAG_PENDIENTE, ots._varbytes(calendario.encode())))
        s.ops.append((0xF0, calendario.encode(), hijo))
        ramas.append(s)
    combinado = ots.Sello(digest)
    for r in ramas:
        combinado.fusionar(r)
    archivo = ots.archivo(digest, combinado)
    _, releido = ots.leer_archivo(archivo)
    assert sorted(c for _, c, _ in ots.pendientes(releido)) == ["https://a.example", "https://b.example"]


def test_rechaza_archivos_que_no_son_ots():
    with pytest.raises(ots.PruebaInvalida):
        ots.leer_archivo(b"no es una prueba")
    datos = _leer("pendiente.json.ots")
    with pytest.raises(ots.PruebaInvalida):
        ots.leer_archivo(datos[:-5])  # truncada


def test_completar_anclaje_confirma_solo_si_coincide_con_bitcoin(monkeypatch):
    """Un sello pendiente pasa a confirmado_bitcoin cuando la prueba completa coincide con el bloque."""
    digest, completo = ots.leer_archivo(_leer("hello-world.txt.ots"))
    pendiente = ots.Sello(digest)
    pendiente.atestaciones.append((ots.TAG_PENDIENTE, ots._varbytes(b"https://alice.example")))

    async def completar_falso(sello, timeout):
        sello.fusionar(completo)  # lo que devolvería el calendario
        return 1
    monkeypatch.setattr(ots, "completar", completar_falso)
    anclaje = {"estado": "pendiente_bitcoin", "fecha": "2015-05-28T00:00:00.000Z",
               "prueba_b64": base64.b64encode(ots.escribir_sello(pendiente)).decode()}

    monkeypatch.setattr(ots, "bloque_bitcoin", _explorador(MERKLE_358391))
    nuevo = asyncio.run(registro.completar_anclaje(digest.hex(), anclaje))
    assert nuevo["estado"] == "confirmado_bitcoin" and nuevo["bitcoin"]["altura"] == 358391
    assert nuevo["fecha"] == anclaje["fecha"]  # la fecha del sello no cambia
    _, final = ots.leer_archivo(registro.archivo_ots(digest.hex(), nuevo["prueba_b64"]))
    assert ots.bitcoin(final) and ots.pendientes(final)

    monkeypatch.setattr(ots, "bloque_bitcoin", _explorador("22" * 32))
    assert asyncio.run(registro.completar_anclaje(digest.hex(), anclaje))["estado"] == "invalido"


def test_completar_anclaje_sin_bitcoin_no_cambia_nada(monkeypatch):
    async def sin_bloque(sello, timeout):
        return 0
    monkeypatch.setattr(ots, "completar", sin_bloque)
    digest, _ = ots.leer_archivo(_leer("pendiente.json.ots"))
    prueba = base64.b64encode(_leer("pendiente.json.ots")[len(ots.MAGIC) + 2 + 32:]).decode()
    assert asyncio.run(registro.completar_anclaje(digest.hex(), {"prueba_b64": prueba})) is None


def test_huella_del_mensaje_igual_que_trim_del_navegador():
    # trim() de JavaScript quita ﻿ y no quita \x1c ni \x85 (str.strip() de Python sí)
    assert registro.normalizar_mensaje("﻿ hola \r\n") == "hola"
    assert registro.normalizar_mensaje("\x1chola\x85") == "\x1chola\x85"
