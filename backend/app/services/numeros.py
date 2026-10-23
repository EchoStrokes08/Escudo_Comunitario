"""
Consulta y clasificación de números telefónicos reportados (vishing).

Tres fuentes se combinan, siempre de forma explicable:

  1. Registro de confianza (`app/data/numeros.json`): líneas oficiales de
     entidades (para no tratarlas como fraude) y números reportados por
     autoridades o entidades, cada uno con su fuente y enlace verificable.
  2. Reportes comunitarios: veces que los vecinos ya reportaron ese número en
     la cadena de certificados (`indicadores/{tipo}:{valor}` en Firestore).
  3. Señales del propio número: oculto, inválido, internacional, línea
     gratuita, móvil o fijo colombiano.

El resultado nunca afirma que un número sea seguro: un número sin reportes
puede ser nuevo, y un número real puede estar falsificado (spoofing). Por eso
la recomendación siempre invita a verificar y a no compartir códigos.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.riesgo import nivel

# Un número de 10 dígitos se muestra legible; los cortos (123) se dejan igual.
_RUTA_DATOS = Path(__file__).resolve().parent.parent / "data" / "numeros.json"

# Categorías de reporte y el peso que aportan al riesgo del número.
CATEGORIAS: dict[str, dict] = {
    "vishing": {"nombre": "Vishing (estafa por llamada)", "peso": 60, "tipo": "vishing"},
    "extorsion": {"nombre": "Extorsión o amenaza", "peso": 60, "tipo": "extorsion"},
    "sim_swapping": {"nombre": "SIM swapping (robo de la línea)", "peso": 55, "tipo": "sim_swapping"},
    "phishing": {"nombre": "Phishing", "peso": 50, "tipo": "phishing"},
    "telemercadeo": {"nombre": "Telemercadeo no deseado", "peso": 20, "tipo": None},
    "otro": {"nombre": "Otro fraude", "peso": 40, "tipo": "otro"},
}

_LINEAS_CORTAS = {"123", "122", "165", "141", "119", "195", "144", "150", "112"}
_OCULTO = ("oculto", "privado", "desconocido", "sin numero", "sin número", "no disponible",
           "anonimo", "anónimo", "no identificado")


class NumeroInvalido(ValueError):
    """El texto recibido no contiene un número consultable."""


def normalizar_numero(entrada: str | None) -> str:
    """
    Deja solo dígitos y quita el indicativo de Colombia (57) cuando sobra.

    Acepta '+57 300 123 4567', '300-123-4567', '573001234567', '601 592 0400'
    o '018000 910165'. Devuelve 'oculto' para números privados y '' si no hay
    ningún dígito.
    """
    texto = str(entrada or "").strip().lower()
    if not texto:
        return ""
    if any(palabra in texto for palabra in _OCULTO):
        return "oculto"

    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return ""
    if digitos.startswith("0057"):
        digitos = digitos[4:]
    elif digitos.startswith("57") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    return digitos[:15]


def formato_visible(numero: str) -> str:
    """3001234567 → '300 123 4567'; 6015920400 → '601 592 0400'."""
    if numero == "oculto":
        return "Número oculto o privado"
    if len(numero) == 10 and numero.startswith("3"):
        return f"{numero[:3]} {numero[3:6]} {numero[6:]}"
    if len(numero) == 10 and numero.startswith("60"):
        return f"{numero[:3]} {numero[3:6]} {numero[6:]}"
    if len(numero) == 12 and numero.startswith("018000"):
        return f"018000 {numero[6:]}"
    return numero


def tipo_linea(numero: str) -> str:
    """Tipo de línea deducible del propio número (sin consultar al operador)."""
    if numero == "oculto":
        return "número oculto o privado"
    if numero in _LINEAS_CORTAS:
        return "línea de emergencia o atención"
    if numero.startswith("018000") or numero.startswith("01800"):
        return "línea gratuita nacional"
    if re.fullmatch(r"3\d{9}", numero):
        return "móvil Colombia"
    if re.fullmatch(r"60[1-8]\d{7}", numero):
        return "fijo Colombia"
    if len(numero) < 7:
        return "número corto o incompleto"
    return "internacional o no geográfico"


def es_valido(numero: str) -> bool:
    if numero == "oculto":
        return False
    if re.fullmatch(r"3\d{9}", numero):
        return True
    if re.fullmatch(r"60[1-8]\d{7}", numero):
        return True
    if re.fullmatch(r"01800\d{7}", numero):
        return True
    if numero in _LINEAS_CORTAS:
        return True
    return 7 <= len(numero) <= 15


@lru_cache(maxsize=1)
def _leer() -> dict:
    """Carga el registro una vez; si el archivo falta, el servicio sigue operando."""
    try:
        with open(_RUTA_DATOS, encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        datos = {}
    return {
        "version": datos.get("version", 1),
        "actualizado": datos.get("actualizado", ""),
        "nota": datos.get("nota", ""),
        "fuentes": {f.get("id"): f for f in datos.get("fuentes", []) if f.get("id")},
        "confiables": [e for e in datos.get("numeros_confiables", []) if e.get("numero")],
        "reportados": [e for e in datos.get("numeros_reportados", []) if e.get("numero")],
    }


def recargar() -> None:
    """Olvida el registro en memoria (después de importar un dataset nuevo)."""
    _leer.cache_clear()


def fuentes_publicas() -> dict:
    """Metadatos del registro para mostrar de dónde sale cada dato."""
    datos = _leer()
    # Solo se muestran las fuentes que respaldan alguna entrada (más la comunidad,
    # cuyos conteos viven en Firestore). Así nadie cree que una fuente vacía
    # aportó datos.
    usadas = {e.get("fuente") for e in datos["confiables"] + datos["reportados"] if e.get("fuente")}
    return {
        "version": datos["version"],
        "actualizado": datos["actualizado"],
        "nota": datos["nota"],
        "confiables": len(datos["confiables"]),
        "reportados": len(datos["reportados"]),
        "fuentes": [
            {"id": f["id"], "nombre": f.get("nombre", f["id"]), "url": f.get("url", ""),
             "tipo": f.get("tipo", "otra")}
            for f in datos["fuentes"].values()
            if f["id"] in usadas or f["id"] == "comunidad"
        ],
    }


def _fuente(datos: dict, entrada: dict) -> dict:
    fuente = datos["fuentes"].get(entrada.get("fuente"), {})
    return {
        "id": entrada.get("fuente", ""),
        "nombre": fuente.get("nombre") or entrada.get("fuente") or "Sin fuente",
        "url": entrada.get("url") or fuente.get("url", ""),
        "tipo": fuente.get("tipo", "otra"),
    }


def _comunidad(numero: str) -> int:
    """Veces que la comunidad reportó ese número (0 si Firestore no responde)."""
    try:
        from app.services import firebase_db

        claves = [("telefono", numero)]
        return int(firebase_db.consultar_indicadores(claves).get(("telefono", numero), 0))
    except Exception:
        return 0


def analizar_numero(numero: str, *, veces_comunidad: int | None = None,
                    datos: dict | None = None) -> dict:
    """
    Clasifica un número con las tres fuentes. Devuelve riesgo, nivel, confianza,
    factores explicables, coincidencias con su fuente y recomendación.

    `veces_comunidad` permite pasar el conteo ya consultado (evita otra lectura);
    `datos` permite inyectar un registro en pruebas.
    """
    canon = normalizar_numero(numero)
    if not canon:
        raise NumeroInvalido("Escribe un número de teléfono (puede incluir +57 y espacios).")

    datos = datos or _leer()
    confiables = [c for c in datos["confiables"] if normalizar_numero(c["numero"]) == canon]
    reportados = [r for r in datos["reportados"] if normalizar_numero(r["numero"]) == canon]
    comunidad = _comunidad(canon) if veces_comunidad is None else max(0, int(veces_comunidad))

    factores: list[dict] = []
    causas: list[str] = []
    coincidencias: list[dict] = []
    tipo_sugerido: str | None = None

    # 1) Línea oficial: se reconoce para no estigmatizarla, con la advertencia de spoofing.
    if confiables and not reportados:
        entidad = confiables[0].get("entidad") or "una entidad oficial"
        factores_oficiales = [{"tipo": "info", "texto": f"Línea oficial registrada: {entidad}"}]
        if comunidad:
            factores_oficiales.append({
                "tipo": "alerta",
                "texto": f"{comunidad} {'vecino reportó' if comunidad == 1 else 'vecinos reportaron'} "
                         "llamadas de este número: pueden estar falsificándolo (spoofing)"})
        return {
            "numero": canon,
            "visible": formato_visible(canon),
            "valido": True,
            "tipo_linea": tipo_linea(canon),
            "pais": "Colombia",
            "nivel_riesgo": 0,
            "nivel": "bajo",
            "confianza": 95,
            "reportado": False,
            "reportes_comunidad": comunidad,
            "coincidencias": [],
            "confiable": {"entidad": entidad, "nota": confiables[0].get("nota", ""),
                          "url": confiables[0].get("url", "")},
            "tipo_sugerido": None,
            "factores": factores_oficiales,
            "causas": [],
            "recomendacion": "Es una línea oficial registrada. Aun así, ninguna entidad pide claves, "
                             "códigos ni transferencias por teléfono: si te los piden, cuelga y llama tú "
                             "al número que aparece en la tarjeta o en la app oficial.",
            "aviso": "Los números se pueden falsificar (spoofing): que la pantalla muestre una línea "
                     "oficial no garantiza que quien llama sea esa entidad.",
        }

    # 2) Señales propias del número.
    riesgo = 0
    if canon == "oculto":
        riesgo = 55
        factores.append({"tipo": "sube", "texto": "El número está oculto o es privado: no se puede verificar"})
        causas.append("La llamada entrante no muestra número: los estafadores lo ocultan para no ser rastreados")
    elif not es_valido(canon):
        riesgo = 45
        factores.append({"tipo": "sube", "texto": "El número no tiene un formato válido en Colombia"})
        causas.append("El número no corresponde a un móvil o fijo colombiano válido")
    elif tipo_linea(canon).startswith("internacional"):
        riesgo = 25
        factores.append({"tipo": "info", "texto": "Es un número internacional o no geográfico"})
    else:
        riesgo = 10
        factores.append({"tipo": "info", "texto": f"Formato válido: {tipo_linea(canon)}"})

    # 3) Números reportados por autoridades o entidades (con fuente verificable).
    if reportados:
        mejor = max(reportados, key=lambda r: CATEGORIAS.get(r.get("categoria"), {}).get("peso", 30))
        categoria = CATEGORIAS.get(mejor.get("categoria"), CATEGORIAS["otro"])
        fuentes_distintas = {r.get("fuente") for r in reportados if r.get("fuente")}
        peso = categoria["peso"] + min(20, max(0, len(fuentes_distintas) - 1) * 8)
        if any(_fuente(datos, r).get("tipo") == "oficial" for r in reportados):
            peso += 10
        riesgo = max(riesgo, min(100, peso))
        tipo_sugerido = categoria["tipo"]
        for r in reportados:
            f = _fuente(datos, r)
            coincidencias.append({
                "categoria": r.get("categoria", "otro"),
                "categoria_nombre": categoria["nombre"],
                "fuente": f["nombre"],
                "url": f["url"],
                "fecha": r.get("fecha", ""),
                "descripcion": r.get("descripcion", ""),
                "demo": bool(r.get("demo")),
            })
        factores.append({"tipo": "sube", "texto": f"Reportado como {categoria['nombre']} por "
                                                   f"{', '.join(sorted(fuentes_distintas)) or 'una fuente registrada'}"})
        causas.append(f"El número ya fue reportado por {categoria['nombre'].lower()} en una fuente registrada")
        if any(r.get("demo") for r in reportados):
            factores.append({"tipo": "alerta", "texto": "Incluye datos de demostración: no son reportes reales"})

    # 4) Reportes de la comunidad (efecto red).
    if comunidad:
        # Un solo reporte ya es motivo de precaución; cada uno adicional sube el piso.
        riesgo = max(riesgo, min(85, 40 + (comunidad - 1) * 6))
        factores.append({"tipo": "sube", "texto": f"Reportado por {comunidad} "
                                                   f"{'vecino' if comunidad == 1 else 'vecinos'} de la comunidad"})
        causas.append(f"{comunidad} {'persona ya reportó' if comunidad == 1 else 'personas ya reportaron'} "
                      "este número en Escudo Comunitario")
        if not tipo_sugerido:
            tipo_sugerido = "vishing"

    riesgo = max(0, min(100, int(round(riesgo))))
    nivel_riesgo = nivel(riesgo)
    reportado = bool(reportados or comunidad)
    confianza = 35 + (25 if reportados else 0) + (15 if comunidad else 0) + (10 if comunidad >= 2 else 0)
    confianza = max(20, min(95, confianza))

    if nivel_riesgo == "alto":
        recomendacion = ("No devuelvas la llamada ni compartas códigos. Reporta el número y, si ya diste "
                         "datos o dinero, llama a tu banco y al 123.")
    elif nivel_riesgo == "medio":
        recomendacion = ("Desconfía y verifica por un canal oficial. No dictes códigos, no instales apps de "
                         "control remoto y no transfieras a cuentas que te den por teléfono.")
    else:
        recomendacion = ("No hay reportes de este número, pero eso no garantiza que sea seguro. Si la llamada "
                         "pide dinero, códigos, claves o instalar una app, es fraude: cuelga y verifica.")

    return {
        "numero": canon,
        "visible": formato_visible(canon),
        "valido": canon != "oculto" and es_valido(canon),
        "tipo_linea": tipo_linea(canon),
        "pais": ("Colombia" if (canon in _LINEAS_CORTAS or canon.startswith("018000")
                               or "Colombia" in tipo_linea(canon)) else "No determinado"),
        "nivel_riesgo": riesgo,
        "nivel": nivel_riesgo,
        "confianza": confianza,
        "reportado": reportado,
        "reportes_comunidad": comunidad,
        "coincidencias": coincidencias,
        "confiable": None,
        "tipo_sugerido": tipo_sugerido,
        "factores": factores,
        "causas": causas[:5],
        "recomendacion": recomendacion,
        "aviso": ("Los números se pueden falsificar (spoofing): que la pantalla muestre un número conocido "
                  "no garantiza quién llama. Un número sin reportes tampoco es una garantía de seguridad."),
    }


def hallazgo(analisis: dict) -> dict | None:
    """
    Convierte una coincidencia del registro en un hallazgo del flujo de reportes.
    Solo se genera si el número está en el registro (los reportes comunitarios ya
    los agrega verificador.py y no se deben contar dos veces).
    """
    if not analisis or not analisis.get("coincidencias"):
        return None
    primera = analisis["coincidencias"][0]
    return {
        "tipo": "telefono",
        "valor": analisis["numero"],
        "detalle": f"Número reportado como {primera['categoria_nombre'].lower()}",
        "fuente": "Registro de números reportados",
        "gravedad": 0,  # el riesgo del número se aplica una sola vez en puntuacion.calcular
        "sugiere": analisis.get("tipo_sugerido"),
        "simulada": all(c.get("demo") for c in analisis["coincidencias"]),
    }
