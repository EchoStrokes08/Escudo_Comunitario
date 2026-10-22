"""
Evaluación del detector con un conjunto etiquetado (tests/datos/evaluacion.jsonl).

Mide qué tan bien acierta el flujo completo (IA + fuentes abiertas + puntuación),
sin escribir nada en la base de datos:

  - Exactitud, precisión, sensibilidad (recall), F1 y tasa de falsos positivos
  - Matriz de confusión y acierto del TIPO de fraude
  - Calibración de la confianza: ¿un caso con 80 % de confianza acierta ~80 % de las veces?

    cd backend
    python scripts/evaluar.py                      # motor configurado en .env (LLM con respaldo)
    python scripts/evaluar.py --motor heuristico   # solo el análisis local (rápido, sin claves)
    python scripts/evaluar.py --con-red            # consulta también RDAP, OpenPhish… (más lento)
    python scripts/evaluar.py --salida ../docs/evaluacion.md

Por defecto NO consulta la red (resultados reproducibles) y desactiva la lista de
referencia de demostración, para que ningún mensaje acierte "por estar en la lista".
"""
import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.core.config import settings  # noqa: E402
from app.core.riesgo import UMBRAL_MEDIO  # noqa: E402
from app.services import procesamiento, verificador  # noqa: E402
from app.services.orientacion import nombre_tipo  # noqa: E402

DATOS = RAIZ / "tests" / "datos" / "evaluacion.jsonl"


def cargar(ruta: Path = DATOS) -> list[dict]:
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


def preparar(motor: str | None, con_red: bool):
    if motor:
        settings.LLM_PROVIDER = motor
    verificador.DOMINIOS_REFERENCIA.clear()
    verificador.CUENTAS_REFERENCIA.clear()
    if not con_red:
        async def _nada(*_a, **_k):
            return None

        async def _sin_feed(*_a, **_k):
            return set()
        verificador._rdap = _nada
        verificador._expandir = _nada
        verificador._urlhaus = _nada
        verificador._hosts_openphish = _sin_feed
        settings.GOOGLE_SAFE_BROWSING_KEY = None
        settings.URLHAUS_AUTH_KEY = None


async def evaluar_caso(caso: dict, pausa: float) -> dict:
    inicio = time.monotonic()
    r = await procesamiento.analizar(caso["texto"], [], historial=None)
    if pausa:
        await asyncio.sleep(pausa)  # respeta los límites de las APIs gratuitas
    riesgo = r["puntaje"]["nivel_riesgo"]
    predicho = riesgo >= UMBRAL_MEDIO
    return {
        **caso,
        "riesgo": riesgo,
        "confianza": r["puntaje"]["confianza"],
        "predicho": predicho,
        "acierto": predicho == caso["fraude"],
        "tipo_predicho": r["tipo"],
        "motor": r["analisis"].get("motor", ""),
        "segundos": round(time.monotonic() - inicio, 2),
    }


def metricas(res: list[dict]) -> dict:
    vp = sum(r["fraude"] and r["predicho"] for r in res)
    fp = sum(not r["fraude"] and r["predicho"] for r in res)
    fn = sum(r["fraude"] and not r["predicho"] for r in res)
    vn = sum(not r["fraude"] and not r["predicho"] for r in res)
    div = lambda a, b: a / b if b else 0.0  # noqa: E731
    precision, recall = div(vp, vp + fp), div(vp, vp + fn)
    fraudes_detectados = [r for r in res if r["fraude"] and r["predicho"]]

    # Calibración: por rangos de confianza, ¿qué porcentaje acertó?
    rangos = []
    for bajo, alto in ((0, 50), (50, 75), (75, 90), (90, 101)):
        grupo = [r for r in res if bajo <= r["confianza"] < alto]
        if grupo:
            rangos.append({"rango": f"{bajo}–{min(alto, 100)} %", "casos": len(grupo),
                           "confianza_media": round(sum(r["confianza"] for r in grupo) / len(grupo), 1),
                           "acierto": round(100 * div(sum(r["acierto"] for r in grupo), len(grupo)), 1)})
    ece = sum(g["casos"] * abs(g["confianza_media"] - g["acierto"]) for g in rangos) / max(len(res), 1)

    return {
        "casos": len(res), "fraudes": vp + fn, "legitimos": fp + vn,
        "exactitud": round(100 * div(vp + vn, len(res)), 1),
        "precision": round(100 * precision, 1),
        "sensibilidad": round(100 * recall, 1),
        "f1": round(100 * div(2 * precision * recall, precision + recall), 1),
        "falsos_positivos_pct": round(100 * div(fp, fp + vn), 1),
        "matriz": {"vp": vp, "fp": fp, "fn": fn, "vn": vn},
        "tipo_correcto_pct": round(100 * div(sum(r["tipo_predicho"] == r["tipo"] for r in fraudes_detectados),
                                             len(fraudes_detectados)), 1),
        "calibracion": rangos,
        "error_calibracion": round(ece, 1),
        "segundos_promedio": round(sum(r["segundos"] for r in res) / max(len(res), 1), 2),
        "motores": dict(Counter(r["motor"] for r in res)),
    }


def informe(m: dict, res: list[dict], motor: str, con_red: bool) -> str:
    l = [f"# Evaluación del detector · {date.today().isoformat()}", "",
         f"- Conjunto: `tests/datos/evaluacion.jsonl`: **{m['casos']} mensajes** ({m['fraudes']} fraudes, "
         f"{m['legitimos']} legítimos), sintéticos y escritos a partir de modalidades frecuentes en Colombia.",
         f"- Motor: `{motor}` · usado en la práctica: {', '.join(f'{k} ({v})' for k, v in m['motores'].items())}",
         f"- Fuentes en red: {'sí' if con_red else 'no (reproducible)'} · lista de demostración: desactivada",
         f"- Umbral de alerta: riesgo ≥ {UMBRAL_MEDIO} %", ""]
    if motor != "heuristico" and "llm" not in m["motores"]:
        l += ["> ⚠️ **La IA no respondió en ningún mensaje** (¿falta GEMINI_API_KEY / GROQ_API_KEY en .env?): "
              "estas cifras son del análisis local de respaldo, no del agente de IA.", ""]
    l += [

         "| Métrica | Valor |", "|---|---|",
         f"| Exactitud | **{m['exactitud']} %** |",
         f"| Precisión (de lo que alertó, cuánto era fraude) | {m['precision']} % |",
         f"| Sensibilidad (de los fraudes, cuántos detectó) | {m['sensibilidad']} % |",
         f"| F1 | {m['f1']} % |",
         f"| Falsos positivos (legítimos marcados como fraude) | {m['falsos_positivos_pct']} % |",
         f"| Tipo de fraude correcto (en fraudes detectados) | {m['tipo_correcto_pct']} % |",
         f"| Error de calibración de la confianza (ECE) | {m['error_calibracion']} puntos |",
         f"| Tiempo promedio por mensaje | {m['segundos_promedio']} s |", "",
         "**Matriz de confusión**", "",
         "| | Predijo fraude | Predijo legítimo |", "|---|---|---|",
         f"| Es fraude | {m['matriz']['vp']} | {m['matriz']['fn']} |",
         f"| Es legítimo | {m['matriz']['fp']} | {m['matriz']['vn']} |", "",
         "**Calibración de la confianza**", "",
         "| Rango de confianza | Casos | Confianza media | Acierto real |", "|---|---|---|---|"]
    l += [f"| {g['rango']} | {g['casos']} | {g['confianza_media']} % | {g['acierto']} % |" for g in m["calibracion"]]
    errores = [r for r in res if not r["acierto"]]
    if errores:
        l += ["", f"**Errores ({len(errores)})**", "", "| Id | Esperado | Riesgo | Mensaje |", "|---|---|---|---|"]
        l += [f"| {r['id']} | {'fraude' if r['fraude'] else 'legítimo'} ({nombre_tipo(r['tipo'])}) | {r['riesgo']} % | "
              f"{r['texto'][:90].replace('|', '/')}… |" for r in errores]
    return "\n".join(l) + "\n"


async def principal():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--motor", choices=["groq", "gemini", "openai", "heuristico"], help="Motor de IA a evaluar")
    p.add_argument("--con-red", action="store_true", help="Consultar RDAP, OpenPhish, etc.")
    p.add_argument("--limite", type=int, help="Evaluar solo los primeros N mensajes")
    p.add_argument("--pausa", type=float, default=0.0, help="Segundos entre mensajes (cuotas de APIs gratis)")
    p.add_argument("--salida", type=Path, help="Guardar el informe en Markdown (y un .json con el detalle)")
    args = p.parse_args()

    preparar(args.motor, args.con_red)
    casos = cargar()[:args.limite]
    res = []
    for i, caso in enumerate(casos, 1):
        res.append(await evaluar_caso(caso, args.pausa))
        print(f"\r{i}/{len(casos)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    m = metricas(res)
    texto = informe(m, res, settings.LLM_PROVIDER, args.con_red)
    print(texto)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(texto, encoding="utf-8")
        args.salida.with_suffix(".json").write_text(
            json.dumps({"metricas": m, "resultados": res}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(principal())
