"""Consulta de números (vishing): normalización, riesgo explicable y API."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import numeros

DATOS = {
    "fuentes": {
        "policia": {"id": "policia", "nombre": "Policía Nacional", "url": "https://www.policia.gov.co/",
                    "tipo": "oficial"},
        "comunidad": {"id": "comunidad", "nombre": "Comunidad", "url": "/reportar", "tipo": "comunitaria"},
    },
    "confiables": [
        {"numero": "123", "entidad": "Policía Nacional", "categoria": "emergencias", "fuente": "policia",
         "url": "https://www.policia.gov.co/", "nota": "Emergencias"},
    ],
    "reportados": [
        {"numero": "3001112233", "categoria": "vishing", "fuente": "policia", "fecha": "2026-01-15",
         "descripcion": "Llama haciéndose pasar por el banco y pide el código.", "demo": False},
    ],
}


def test_normaliza_formatos_colombianos():
    assert numeros.normalizar_numero("+57 300 123 4567") == "3001234567"
    assert numeros.normalizar_numero("300-123-4567") == "3001234567"
    assert numeros.normalizar_numero("573001234567") == "3001234567"
    assert numeros.normalizar_numero("(601) 592 0400") == "6015920400"
    assert numeros.normalizar_numero("018000 910165") == "018000910165"
    assert numeros.normalizar_numero("número oculto") == "oculto"
    assert numeros.normalizar_numero("") == ""


def test_tipo_de_linea():
    assert numeros.tipo_linea("3001234567") == "móvil Colombia"
    assert numeros.tipo_linea("6015920400") == "fijo Colombia"
    assert numeros.tipo_linea("018000910165") == "línea gratuita nacional"
    assert numeros.tipo_linea("123") == "línea de emergencia o atención"
    assert numeros.tipo_linea("oculto") == "número oculto o privado"


def test_linea_oficial_no_se_marca_como_fraude():
    resultado = numeros.analizar_numero("123", datos=DATOS, veces_comunidad=0)
    assert resultado["nivel_riesgo"] == 0
    assert resultado["nivel"] == "bajo"
    assert resultado["confiable"]["entidad"] == "Policía Nacional"
    assert "spoofing" in resultado["aviso"]


def test_numero_reportado_por_autoridad_es_riesgo_alto():
    resultado = numeros.analizar_numero("300 111 2233", datos=DATOS, veces_comunidad=0)
    assert resultado["reportado"] is True
    assert resultado["nivel"] == "alto"
    assert resultado["tipo_sugerido"] == "vishing"
    assert resultado["coincidencias"][0]["fuente"] == "Policía Nacional"
    assert any("vishing" in causa.lower() for causa in resultado["causas"])


def test_un_reporte_comunitario_ya_es_precaucion():
    uno = numeros.analizar_numero("3009998877", datos={"fuentes": {}, "confiables": [], "reportados": []},
                                  veces_comunidad=1)
    cinco = numeros.analizar_numero("3009998877", datos={"fuentes": {}, "confiables": [], "reportados": []},
                                    veces_comunidad=6)
    assert uno["reportado"] is True and uno["nivel"] == "medio"
    assert cinco["nivel"] == "alto"
    assert cinco["nivel_riesgo"] > uno["nivel_riesgo"]


def test_numero_oculto_e_invalido():
    oculto = numeros.analizar_numero("oculto", datos=DATOS, veces_comunidad=0)
    corto = numeros.analizar_numero("12", datos=DATOS, veces_comunidad=0)
    assert oculto["nivel"] == "medio" and oculto["valido"] is False
    assert corto["nivel"] == "medio" and corto["valido"] is False
    with pytest.raises(numeros.NumeroInvalido):
        numeros.analizar_numero("", datos=DATOS)


def test_hallazgo_solo_para_registro_no_para_comunidad():
    registro = numeros.analizar_numero("3001112233", datos=DATOS, veces_comunidad=0)
    comunidad = numeros.analizar_numero("3009998877", datos={"fuentes": {}, "confiables": [], "reportados": []},
                                        veces_comunidad=3)
    assert numeros.hallazgo(registro)["sugiere"] == "vishing"
    assert numeros.hallazgo(registro)["gravedad"] == 0
    assert numeros.hallazgo(comunidad) is None


def test_api_consulta_y_fuentes(monkeypatch):
    monkeypatch.setattr(numeros, "_comunidad", lambda _numero: 0)
    cliente = TestClient(app)

    respuesta = cliente.get("/api/numeros/consultar", params={"numero": "123"})
    assert respuesta.status_code == 200
    assert respuesta.json()["nivel_riesgo"] == 0

    fuentes = cliente.get("/api/numeros/fuentes")
    assert fuentes.status_code == 200
    assert fuentes.json()["confiables"] >= 1

    invalido = cliente.get("/api/numeros/consultar", params={"numero": "sin-digitos"})
    assert invalido.status_code == 400
