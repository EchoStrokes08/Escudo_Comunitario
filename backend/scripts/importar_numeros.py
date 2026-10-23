"""
Importa números reportados (o líneas oficiales) al registro del Escudo.

El registro vive en `app/data/numeros.json` y cada entrada conserva su fuente y
su enlace para que cualquiera pueda verificarla. Este script NO inventa datos:
solo normaliza, valida, deduplica y escribe lo que venga de un CSV o JSON.

Ejemplos:

    # Números reportados por una fuente oficial (CSV con encabezados)
    python scripts/importar_numeros.py --archivo datos_policia.csv \
        --fuente policia --nombre-fuente "Policía Nacional" \
        --url https://www.policia.gov.co/ --oficial --categoria vishing

    # Líneas oficiales (para que no se marquen como fraude)
    python scripts/importar_numeros.py --archivo lineas_oficiales.csv \
        --tipo confiable --fuente sic --nombre-fuente "SIC" \
        --url https://www.sic.gov.co/ --oficial

    # Datos de demostración, claramente marcados como tales
    python scripts/importar_numeros.py --archivo ../docs/ejemplos/numeros_demo.csv \
        --fuente comunidad --categoria vishing --demo

    # Ver el estado del registro o quitar un número
    python scripts/importar_numeros.py --listar
    python scripts/importar_numeros.py --quitar 3001234567

Encabezados aceptados (CSV): numero, categoria, fuente, url, fecha, descripcion,
entidad, demo. También acepta los nombres en inglés phone/category/source/date.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.services.numeros import CATEGORIAS, normalizar_numero  # noqa: E402

REGISTRO = RAIZ / "app" / "data" / "numeros.json"

ALIAS = {
    "numero": ("numero", "número", "telefono", "teléfono", "celular", "linea", "línea",
               "phone", "number", "msisdn"),
    "categoria": ("categoria", "categoría", "tipo", "category", "type"),
    "fuente": ("fuente", "source", "entidad", "entity"),
    "url": ("url", "enlace", "link", "fuente_url"),
    "fecha": ("fecha", "date", "actualizado", "updated"),
    "descripcion": ("descripcion", "descripción", "detalle", "nota", "observacion",
                    "observación", "description"),
    "entidad": ("entidad", "entity", "nombre", "name"),
    "demo": ("demo", "demostracion", "demostración", "es_demo"),
}


def _clave(fila: dict, campo: str) -> str:
    for alias in ALIAS[campo]:
        if alias in fila and str(fila[alias] or "").strip():
            return str(fila[alias]).strip()
    # Encabezados con mayúsculas/espacios
    normalizados = {str(k).strip().lower(): v for k, v in fila.items()}
    for alias in ALIAS[campo]:
        if alias in normalizados and str(normalizados[alias] or "").strip():
            return str(normalizados[alias]).strip()
    return ""


def _leer_archivo(ruta: Path) -> list[dict]:
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo: {ruta}")
    if ruta.suffix.lower() == ".csv":
        with open(ruta, encoding="utf-8-sig", newline="") as archivo:
            return list(csv.DictReader(archivo))
    if ruta.suffix.lower() in (".json", ".jsonl"):
        if ruta.suffix.lower() == ".jsonl":
            with open(ruta, encoding="utf-8") as archivo:
                return [json.loads(linea) for linea in archivo if linea.strip()]
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        if isinstance(datos, list):
            return datos
        if isinstance(datos, dict):
            for clave in ("numeros_reportados", "reportados", "numeros", "datos"):
                if isinstance(datos.get(clave), list):
                    return datos[clave]
        raise SystemExit("El JSON debe ser una lista o traer 'numeros_reportados'.")
    raise SystemExit("Formato no soportado: usa .csv, .json o .jsonl")


def _cargar_registro() -> dict:
    if not REGISTRO.exists():
        return {"version": 1, "actualizado": "", "nota": "", "fuentes": [],
                "numeros_confiables": [], "numeros_reportados": []}
    with open(REGISTRO, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    datos.setdefault("fuentes", [])
    datos.setdefault("numeros_confiables", [])
    datos.setdefault("numeros_reportados", [])
    return datos


def _guardar(datos: dict, seco: bool) -> None:
    datos["actualizado"] = date.today().isoformat()
    if seco:
        print("[seco] No se escribió el archivo.")
        return
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix="numeros-", suffix=".json", dir=REGISTRO.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
        os.replace(temporal, REGISTRO)  # escritura atómica
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def _registrar_fuente(datos: dict, fuente_id: str, nombre: str, url: str, tipo: str) -> None:
    for fuente in datos["fuentes"]:
        if fuente.get("id") == fuente_id:
            # No degradar una fuente oficial por una importación comunitaria posterior.
            tipo_final = "oficial" if (tipo == "oficial" or
                                       (fuente.get("tipo") == "oficial" and tipo != "demostracion")) else tipo
            fuente.update({"nombre": nombre or fuente.get("nombre", fuente_id),
                           "url": url or fuente.get("url", ""), "tipo": tipo_final})
            return
    datos["fuentes"].append({"id": fuente_id, "nombre": nombre or fuente_id,
                             "url": url, "tipo": tipo})


def _importar(argumentos: argparse.Namespace) -> None:
    datos = _cargar_registro()
    filas = _leer_archivo(Path(argumentos.archivo))
    tipo_fuente = "demostracion" if argumentos.demo else ("oficial" if argumentos.oficial else "importada")
    _registrar_fuente(datos, argumentos.fuente, argumentos.nombre_fuente, argumentos.url, tipo_fuente)

    if argumentos.reemplazar and argumentos.tipo == "reportado":
        datos["numeros_reportados"] = []

    agregados, actualizados, omitidos = 0, 0, 0
    vistos = {(normalizar_numero(e.get("numero")), e.get("fuente"))
              for e in datos.get("numeros_reportados", [])}
    for fila in filas:
        numero = normalizar_numero(_clave(fila, "numero"))
        if not numero:
            omitidos += 1
            continue
        categoria = _clave(fila, "categoria").lower() or argumentos.categoria
        if argumentos.tipo == "confiable":
            categoria = categoria or "atencion_ciudadana"
        else:
            categoria = categoria or "vishing"
            if categoria not in CATEGORIAS:
                categoria = "otro"
        fuente = _clave(fila, "fuente") or argumentos.fuente
        fecha = _clave(fila, "fecha") or date.today().isoformat()
        descripcion = _clave(fila, "descripcion")
        demo = argumentos.demo or _clave(fila, "demo").lower() in ("1", "true", "si", "sí", "yes")

        if argumentos.tipo == "confiable":
            entidad = _clave(fila, "entidad") or argumentos.nombre_fuente or fuente
            confiables = datos["numeros_confiables"]
            existente = next((e for e in confiables if normalizar_numero(e.get("numero")) == numero), None)
            entrada = {"numero": numero, "entidad": entidad, "categoria": categoria,
                       "fuente": fuente, "url": _clave(fila, "url") or argumentos.url,
                       "nota": descripcion}
            if existente:
                existente.update(entrada)
                actualizados += 1
            else:
                confiables.append(entrada)
                agregados += 1
            continue

        reportados = datos["numeros_reportados"]
        clave = (numero, fuente)
        existente = next((e for e in reportados
                          if normalizar_numero(e.get("numero")) == numero and e.get("fuente") == fuente), None)
        entrada = {"numero": numero, "categoria": categoria, "fuente": fuente,
                   "url": _clave(fila, "url") or argumentos.url, "fecha": fecha,
                   "descripcion": descripcion, "demo": demo}
        if existente:
            existente.update(entrada)
            actualizados += 1
        elif clave in vistos:
            actualizados += 1
        else:
            reportados.append(entrada)
            vistos.add(clave)
            agregados += 1

    _guardar(datos, argumentos.seco)
    print(f"Fuente: {argumentos.fuente} ({tipo_fuente})")
    print(f"Añadidos: {agregados} · actualizados: {actualizados} · omitidos sin número: {omitidos}")
    print(f"Total: {len(datos['numeros_confiables'])} líneas oficiales, "
          f"{len(datos['numeros_reportados'])} números reportados.")


def _listar() -> None:
    datos = _cargar_registro()
    print(f"Registro: {REGISTRO}")
    print(f"Actualizado: {datos.get('actualizado') or 'sin fecha'}")
    print(f"Líneas oficiales: {len(datos['numeros_confiables'])}")
    print(f"Números reportados: {len(datos['numeros_reportados'])}")
    print("Fuentes:")
    for fuente in datos["fuentes"]:
        print(f"  - {fuente.get('id')}: {fuente.get('nombre')} ({fuente.get('tipo')}) {fuente.get('url', '')}")
    if datos["numeros_reportados"]:
        print("Reportados:")
        for entrada in datos["numeros_reportados"]:
            demo = " [demo]" if entrada.get("demo") else ""
            print(f"  - {entrada['numero']} · {entrada.get('categoria')} · {entrada.get('fuente')}{demo}")


def _quitar(numero: str, seco: bool) -> None:
    datos = _cargar_registro()
    canon = normalizar_numero(numero)
    antes = len(datos["numeros_reportados"])
    datos["numeros_reportados"] = [e for e in datos["numeros_reportados"]
                                   if normalizar_numero(e.get("numero")) != canon]
    _guardar(datos, seco)
    print(f"Quitados {antes - len(datos['numeros_reportados'])} registros de {canon}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa números al registro del Escudo Comunitario.")
    parser.add_argument("--archivo", help="CSV/JSON/JSONL con los números")
    parser.add_argument("--fuente", default="importado", help="id de la fuente (p. ej. policia, sic, comunidad)")
    parser.add_argument("--nombre-fuente", default="", help="nombre legible de la fuente")
    parser.add_argument("--url", default="", help="enlace público donde se verifican los datos")
    parser.add_argument("--categoria", default="", help="categoría por defecto (p. ej. vishing, extorsion, atencion_ciudadana)")
    parser.add_argument("--tipo", default="reportado", choices=("reportado", "confiable"),
                        help="'reportado' para números fraudulentos; 'confiable' para líneas oficiales")
    parser.add_argument("--oficial", action="store_true", help="marca la fuente como oficial")
    parser.add_argument("--demo", action="store_true", help="marca los datos como demostración (visible en la UI)")
    parser.add_argument("--reemplazar", action="store_true", help="reemplaza los números reportados antes de importar")
    parser.add_argument("--seco", action="store_true", help="no escribe, solo muestra el resultado")
    parser.add_argument("--listar", action="store_true", help="muestra el estado del registro")
    parser.add_argument("--quitar", metavar="NUMERO", help="elimina un número reportado")
    argumentos = parser.parse_args()

    if argumentos.listar:
        _listar()
        return
    if argumentos.quitar:
        _quitar(argumentos.quitar, argumentos.seco)
        return
    if not argumentos.archivo:
        parser.error("indica --archivo, --listar o --quitar")
    _importar(argumentos)


if __name__ == "__main__":
    main()
