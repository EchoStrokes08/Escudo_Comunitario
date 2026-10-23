"""
Riesgo final y nivel de confianza explicables.

  riesgo     = veredicto del LLM (o del análisis local), protegido contra
               manipulación y reforzado por la evidencia de fuentes abiertas.
  confianza  = qué tan sólida es la evidencia detrás de ese riesgo:
               certeza del modelo + acuerdo entre el LLM y el análisis local
               + confirmaciones externas (RDAP, URLhaus, suplantación de marca,
               reportes comunitarios) − penalización si hay poco contenido.

Cada ajuste deja un "factor" legible para mostrarle a la persona (y al jurado)
por qué el sistema está seguro o no.
"""
from app.core.riesgo import UMBRAL_ALTO, nivel, nivel_confianza


def _limitar(valor: float, minimo: int = 0, maximo: int = 100) -> int:
    return int(max(minimo, min(maximo, round(valor))))


def calcular(analisis: dict, verificacion: dict, texto: str, adjuntos: list[dict],
             numero: dict | None = None) -> dict:
    heur = analisis.get("heuristico") or {}
    usa_llm = analisis.get("motor") == "llm"
    r_llm = analisis["nivel_riesgo"]
    r_heur = heur.get("nivel_riesgo", 0)
    factores: list[dict] = []

    # ---------------- Riesgo ----------------
    riesgo = r_llm
    if usa_llm and r_heur - r_llm >= 40:
        # El LLM dice "tranquilo" pero el texto tiene muchas señales: posible manipulación del prompt
        riesgo = round(0.5 * r_llm + 0.5 * r_heur)
        factores.append({"tipo": "alerta", "texto": "El análisis local encontró más señales que la IA; se tomó el promedio"})

    hallazgos = verificacion.get("hallazgos", [])
    bonus = min(45, sum(h.get("gravedad", 0) for h in hallazgos))
    if bonus:
        riesgo += bonus
        factores.append({"tipo": "sube", "texto": f"Fuentes abiertas confirmaron {len(hallazgos)} "
                                                  f"{'hallazgo' if len(hallazgos) == 1 else 'hallazgos'} (+{bonus})"})

    # El número entrante se evalúa antes de la llamada: un número reportado sube el riesgo
    # aunque el relato sea corto, y una línea oficial no lo baja si el contenido es claro.
    if numero and numero.get("nivel_riesgo") is not None:
        r_numero = int(numero["nivel_riesgo"])
        if numero.get("reportado") or r_numero >= 40:
            # Un número reportado (aunque sea por un vecino) o una señal fuerte del
            # propio número (oculto, inválido) fija un piso de riesgo: no se diluye.
            ajuste = r_numero if numero.get("reportado") else max(0, r_numero - 5)
            riesgo = max(riesgo, min(100, ajuste))
            factores.append({"tipo": "sube", "texto": f"El número consultado tiene riesgo "
                                                      f"{numero.get('nivel', 'alto')} ({r_numero}/100)"})
        elif riesgo >= 40:
            factores.append({"tipo": "info", "texto": "El número no está reportado; el riesgo viene del relato"})
    riesgo = _limitar(riesgo)

    # ---------------- Confianza ----------------
    if usa_llm:
        confianza = 30 + 0.35 * analisis.get("certeza", 60)
        factores.append({"tipo": "info", "texto": f"Análisis con IA ({analisis.get('modelo') or 'LLM'}), "
                                                  f"certeza del modelo {analisis.get('certeza', 60)}%"})
        texto_util = not heur.get("sin_texto_util", False)
        if texto_util:
            diferencia = abs(r_llm - r_heur)
            if diferencia <= 20:
                confianza += 15
                factores.append({"tipo": "sube", "texto": "La IA y el análisis local coinciden"})
            elif diferencia <= 40:
                confianza += 5
            else:
                confianza -= 10
                factores.append({"tipo": "baja", "texto": "La IA y el análisis local no coinciden del todo"})
    else:
        confianza = 30
        factores.append({"tipo": "baja", "texto": "Solo análisis local (sin IA): confianza limitada"})

    externos = [h for h in hallazgos if not h.get("simulada")]
    if externos:
        confianza += min(30, 12 * len(externos))
        fuentes = sorted({h["fuente"] for h in externos})
        factores.append({"tipo": "sube", "texto": "Confirmado por: " + ", ".join(fuentes)})
    simulados = [h for h in hallazgos if h.get("simulada")]
    if simulados:
        confianza += 8

    if numero and numero.get("coincidencias"):
        confianza += 15
        factores.append({"tipo": "sube", "texto": "El número coincide con el registro de números reportados"})
    elif numero and numero.get("reportes_comunidad"):
        confianza += 8
        factores.append({"tipo": "sube", "texto": "Vecinos ya habían reportado este número"})

    poco_contenido = len((texto or "").strip()) < 40 and not adjuntos
    if poco_contenido:
        confianza -= 15
        factores.append({"tipo": "baja", "texto": "Mensaje muy corto: envía el texto completo o una captura"})

    # Un veredicto extremo (muy alto o muy bajo) sin contradicciones es más fiable que uno intermedio
    if riesgo >= UMBRAL_ALTO + 15 or riesgo <= 15:
        confianza += 5

    confianza = _limitar(confianza, 10, 99)
    return {
        "nivel_riesgo": riesgo,
        "nivel": nivel(riesgo),
        "confianza": confianza,
        "nivel_confianza": nivel_confianza(confianza),
        "factores": factores,
    }
