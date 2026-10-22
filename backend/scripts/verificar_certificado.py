"""
Verificación independiente de un certificado de reporte, sin confiar en nuestro servidor.

Comprueba, con fuentes públicas que no controlamos:
  1. Que el SHA-256 del registro (JSON canónico del bloque) es el código del certificado.
  2. Que la prueba OpenTimestamps (.ots) corresponde a ese mismo hash.
  3. Que la prueba llega a un bloque de Bitcoin: completa la prueba con los calendarios
     públicos si hace falta y compara el resultado con la raíz de Merkle real del bloque,
     consultada en blockstream.info y mempool.space.
  4. (Opcional) Que un mensaje es exactamente el que se reportó (--mensaje).

Uso:
    python scripts/verificar_certificado.py <codigo>                       # descarga de la app
    python scripts/verificar_certificado.py --json registro.json --ots registro.json.ots
    python scripts/verificar_certificado.py <codigo> --mensaje "texto del mensaje original"

Equivale a `ots verify registro.json.ots` del cliente oficial de OpenTimestamps
(https://github.com/opentimestamps/opentimestamps-client) o a subir los dos archivos a
https://opentimestamps.org.
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import ots  # noqa: E402
from app.services.registro import hash_mensaje  # noqa: E402

APP_URL = os.getenv("APP_URL", "https://escudocomunitario.vercel.app").rstrip("/")


def _ok(texto: str):
    print(f"  [OK]  {texto}")


def _falla(texto: str):
    print(f"  [X]   {texto}")


async def verificar(registro: bytes, prueba: bytes, codigo: str | None, mensaje: str | None) -> tuple[bool, bool]:
    """Devuelve (válido, confirmado en Bitcoin)."""
    valido = True
    digest = hashlib.sha256(registro).digest()
    print("\n1. Registro (JSON canónico del bloque)")
    if codigo:
        if digest.hex().startswith(codigo.lower()):
            _ok(f"SHA-256 del registro = certificado {digest.hex()}")
        else:
            _falla(f"El SHA-256 del registro ({digest.hex()}) no es el certificado {codigo}")
            valido = False
    else:
        _ok(f"SHA-256 del registro: {digest.hex()}")
    bloque = json.loads(registro)
    print(f"        fecha declarada {bloque.get('fecha')} · altura {bloque.get('altura')} · "
          f"anterior {str(bloque.get('prev'))[:16]}…")

    print("\n2. Prueba OpenTimestamps")
    digest_ots, sello = ots.leer_archivo(prueba)
    if digest_ots == digest:
        _ok("La prueba sella exactamente este registro")
    else:
        _falla(f"La prueba sella otro archivo ({digest_ots.hex()})")
        return False, False
    calendarios = sorted({c for _, c, _ in ots.pendientes(sello)})
    if calendarios:
        print("        calendarios: " + ", ".join(calendarios))

    print("\n3. Bitcoin")
    if not ots.bitcoin(sello):
        completadas = await ots.completar(sello, 15)
        if completadas:
            _ok(f"Prueba completada con {completadas} calendario(s)")
    confirmacion = await ots.verificar_bitcoin(sello, 15)
    if confirmacion is None:
        print("  [..]  Aún pendiente: los calendarios publican en Bitcoin cada pocas horas. "
              "El registro sí está sellado; vuelve a intentarlo más tarde.")
    elif confirmacion["valido"]:
        _ok(f"Existe desde antes del bloque {confirmacion['altura']} de Bitcoin "
            f"({confirmacion['hora_bloque']}), raíz de Merkle comprobada en {confirmacion['fuente']}")
    else:
        _falla(f"La prueba NO coincide con la raíz de Merkle del bloque {confirmacion['altura']}")
        valido = False

    if mensaje is not None:
        print("\n4. Mensaje")
        if hash_mensaje(mensaje) == bloque.get("hash_mensaje"):
            _ok("El mensaje es exactamente el que se reportó")
        else:
            _falla("El mensaje no coincide con la huella registrada")
            valido = False
    return valido, bool(confirmacion and confirmacion["valido"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("codigo", nargs="?", help="Código del certificado (hash completo o prefijo)")
    parser.add_argument("--json", help="registro.json descargado de /verificar")
    parser.add_argument("--ots", help="prueba .ots descargada de /verificar")
    parser.add_argument("--mensaje", help="Texto del mensaje original, para comparar su huella")
    parser.add_argument("--app", default=APP_URL, help=f"URL de la app (por defecto {APP_URL})")
    args = parser.parse_args()

    if args.json and args.ots:
        with open(args.json, "rb") as f:
            registro = f.read()
        with open(args.ots, "rb") as f:
            prueba = f.read()
    elif args.codigo:
        base = f"{args.app.rstrip('/')}/api/verificar/{args.codigo}"
        with httpx.Client(timeout=30) as client:
            registro = client.get(f"{base}/registro.json").raise_for_status().content
            prueba = client.get(f"{base}/prueba.ots").raise_for_status().content
        print(f"Descargado de {args.app} (solo los archivos: la verificación se hace aquí)")
    else:
        parser.error("indica un código o --json y --ots")

    valido, en_bitcoin = asyncio.run(verificar(registro, prueba, args.codigo, args.mensaje))
    print("\nResultado: " + ("NO VERIFICADO" if not valido else
                             "VERIFICADO y anclado en Bitcoin" if en_bitcoin else
                             "VERIFICADO (sello en Bitcoin aún pendiente)"))
    sys.exit(0 if valido else 1)


if __name__ == "__main__":
    main()
