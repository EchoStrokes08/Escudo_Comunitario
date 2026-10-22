"""
El conjunto de evaluación está bien formado y el análisis local (respaldo cuando
no hay IA) no se degrada: casi no da falsas alarmas sobre mensajes legítimos.

    cd backend && python -m pytest -q tests/test_evaluacion.py
"""
import asyncio
import sys
from pathlib import Path

from app.core.config import settings
from app.services import verificador
from app.services.orientacion import TIPOS_FRAUDE

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import evaluar  # noqa: E402


def test_conjunto_bien_formado():
    casos = evaluar.cargar()
    assert len(casos) >= 150
    assert len({c["id"] for c in casos}) == len(casos)
    for c in casos:
        assert c["tipo"] in TIPOS_FRAUDE and isinstance(c["fraude"], bool) and len(c["texto"]) > 20
        assert (c["tipo"] == "legitimo") == (not c["fraude"])
    # Ningún mensaje acierta "por estar en la lista de demostración"
    textos = " ".join(c["texto"] for c in casos)
    assert not any(d in textos for d in verificador.DOMINIOS_REFERENCIA)


def test_heuristico_sin_falsas_alarmas(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "heuristico")
    monkeypatch.setattr(settings, "URLHAUS_AUTH_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_SAFE_BROWSING_KEY", None)

    async def nada(*_a, **_k):
        return None

    async def sin_feed(*_a, **_k):
        return set()
    for nombre in ("_rdap", "_expandir", "_urlhaus"):
        monkeypatch.setattr(verificador, nombre, nada)
    monkeypatch.setattr(verificador, "_hosts_openphish", sin_feed)

    async def todos():
        return [await evaluar.evaluar_caso(c, 0) for c in evaluar.cargar()]
    m = evaluar.metricas(asyncio.run(todos()))
    assert m["falsos_positivos_pct"] <= 5
    assert m["precision"] >= 85


def test_conjunto_de_prueba_separado():
    desarrollo = evaluar.cargar(evaluar.CONJUNTOS["desarrollo"])
    prueba = evaluar.cargar(evaluar.CONJUNTOS["prueba"])
    assert len(prueba) >= 60 and {c["tipo"] for c in prueba} >= {"phishing", "malware", "legitimo"}
    for c in prueba:
        assert c["tipo"] in TIPOS_FRAUDE and (c["tipo"] == "legitimo") == (not c["fraude"])
    # Ningún mensaje de prueba aparece en el de desarrollo (si no, la cifra "honesta" no lo sería)
    assert not {c["texto"] for c in prueba} & {c["texto"] for c in desarrollo}


def test_heuristico_en_conjunto_de_prueba(monkeypatch):
    """Piso de calidad del respaldo local en mensajes que no se usaron para diseñarlo."""
    monkeypatch.setattr(settings, "LLM_PROVIDER", "heuristico")
    monkeypatch.setattr(settings, "URLHAUS_AUTH_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_SAFE_BROWSING_KEY", None)

    async def nada(*_a, **_k):
        return None

    async def sin_feed(*_a, **_k):
        return set()
    for nombre in ("_rdap", "_expandir", "_urlhaus"):
        monkeypatch.setattr(verificador, nombre, nada)
    monkeypatch.setattr(verificador, "_hosts_openphish", sin_feed)

    async def todos():
        return [await evaluar.evaluar_caso(c, 0) for c in evaluar.cargar(evaluar.CONJUNTOS["prueba"])]
    m = evaluar.metricas(asyncio.run(todos()))
    assert m["falsos_positivos_pct"] <= 5 and m["sensibilidad"] >= 80
