"""
Seguimiento del caso (estados encadenados), casos agrupados por indicador,
paquete de evidencia, retroalimentación y respuestas en audio.

    cd backend && python -m pytest -q tests/test_seguimiento.py
"""
import hashlib

import pytest

from app.api import verificacion
from app.core.config import settings
from app.services import seguimiento, voz

from test_flujo import MENSAJE, cliente  # noqa: F401  (fixture compartida)

TOKEN = {"Authorization": "Bearer token-autoridades"}


@pytest.fixture
def api(cliente, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "AUTORIDADES_TOKEN", "token-autoridades")
    return cliente


def _reportar(cliente):
    return cliente.post("/api/reporte-web", json={"mensaje": MENSAJE, "upz": "Tintal Sur"}).json()["certificado"]


def test_estados_encadenados_y_verificables(api):
    cliente, base = api
    h = _reportar(cliente)

    r = cliente.post(f"/api/autoridades/casos/{h}/estado", headers=TOKEN,
                     json={"estado": "remitido", "actor": "CAI Bosa Centro",
                           "nota": "Remitido a Fiscalía. Te contactarán al 3001234567"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [e["estado"] for e in d["seguimiento"]] == ["registrado", "remitido"]
    assert "3001234567" not in d["seguimiento"][1]["nota"]  # la nota pública se anonimiza
    assert base.privado[h]["estado"] == "remitido" and base.publico[h]["estado"] == "remitido"

    # La página pública muestra la línea de tiempo íntegra
    v = cliente.get(f"/api/verificar/{h}").json()
    assert v["tipo"] == "reporte" and v["estado_caso"]["estado"] == "remitido"
    assert all(e["integro"] for e in v["seguimiento"])

    # El bloque de seguimiento es un certificado más: encadenado, verificable y descargable
    s = d["certificado_seguimiento"]
    vs = cliente.get(f"/api/verificar/{s}").json()
    assert vs["tipo"] == "seguimiento" and vs["integro"] and vs["caso"] == h and vs["enlaces"]["anterior_valido"]
    canon = cliente.get(f"/api/verificar/{s}/registro.json").content
    assert hashlib.sha256(canon).hexdigest() == s
    assert cliente.get("/api/cadena/auditoria").json()["valida"]

    # Alguien cambia a mano lo que se le dijo a la víctima → se detecta
    base.registros[s]["nota"] = "Caso archivado"
    assert cliente.get(f"/api/verificar/{h}").json()["seguimiento"][1]["integro"] is False
    # …o la fecha en que se remitió → se rompe la cadena
    base.registros[s]["fecha"] = "2020-01-01T00:00:00.000Z"
    assert not cliente.get("/api/cadena/auditoria").json()["valida"]


def test_cambio_de_estado_validado(api):
    cliente, _ = api
    h = _reportar(cliente)
    url = f"/api/autoridades/casos/{h}/estado"
    cuerpo = {"estado": "en_revision", "actor": "Fiscalía"}
    assert cliente.post(url, json=cuerpo).status_code == 401
    assert cliente.post(url, headers=TOKEN, json={**cuerpo, "estado": "inventado"}).status_code == 400
    assert cliente.post(url, headers=TOKEN, json={**cuerpo, "estado": "registrado"}).status_code == 400
    assert cliente.post(url, headers=TOKEN, json=cuerpo).status_code == 200
    assert cliente.post(url, headers=TOKEN, json=cuerpo).status_code == 409  # ya está en revisión
    casos = cliente.get("/api/autoridades/casos", headers=TOKEN).json()
    assert casos["casos"][0]["estado"] == "en_revision" and "cerrado" in casos["estados"]


def test_bot_estado_y_avisos(api, monkeypatch):
    cliente, base = api
    enviados = []
    monkeypatch.setattr(seguimiento, "enviar_twilio", lambda destino, texto: enviados.append((destino, texto)) or True)

    de = {"From": "whatsapp:+573005556677", "NumMedia": "0"}
    r = cliente.post("/api/whatsapp/webhook", data={**de, "Body": MENSAJE})
    assert "avísame" in r.text
    h = next(iter(base.registros))

    # "Estado de su cuenta…" es un reporte, no el comando
    r = cliente.post("/api/whatsapp/simulador", json={"sesion": "otra-sesion-123", "texto":
                     "Estado de su cuenta Bancolombia: BLOQUEADA. Ingrese a bancolombia-soporte-clientes.xyz"}).json()
    assert r.get("certificado")

    r = cliente.post("/api/whatsapp/webhook", data={**de, "Body": "estado"})
    assert "Reporte registrado" in r.text and h in r.text

    r = cliente.post("/api/whatsapp/webhook", data={**de, "Body": "¡Avísame!"})
    assert "Listo" in r.text and base.avisos == [{"caso": h, "canal": "whatsapp", "destino": "whatsapp:+573005556677"}]

    d = cliente.post(f"/api/autoridades/casos/{h}/estado", headers=TOKEN,
                     json={"estado": "en_investigacion", "actor": "Fiscalía Seccional Bogotá"}).json()
    assert d["victimas_avisadas"] == 1 and "En investigación" in enviados[0][1]

    r = cliente.post("/api/whatsapp/webhook", data={**de, "Body": f"estado {h[:16]}"})
    assert "En investigación" in r.text and "Fiscalía Seccional" in r.text

    # Al cerrar el caso se avisa por última vez y se borra el contacto
    cliente.post(f"/api/autoridades/casos/{h}/estado", headers=TOKEN, json={"estado": "cerrado", "actor": "Fiscalía"})
    assert len(enviados) == 2 and base.avisos == []


def test_chat_web_estado_sin_guardar_contacto(api):
    cliente, base = api
    sesion = {"sesion": "navegador-seguimiento-1"}
    r = cliente.post("/api/whatsapp/simulador", json={**sesion, "texto": MENSAJE}).json()
    assert "estado" in r["mensajes"][1]
    r = cliente.post("/api/whatsapp/simulador", json={**sesion, "texto": "avisame"}).json()
    assert "/verificar/" in r["mensajes"][0] and base.avisos == []


def test_casos_agrupados_y_evidencia(api):
    cliente, _ = api
    certificados = [_reportar(cliente) for _ in range(3)]
    grupos = cliente.get("/api/autoridades/agrupados", headers=TOKEN).json()["grupos"]
    cuenta = next(g for g in grupos if g["valor"] == "3001234567")
    assert cuenta["veces"] == 3 and cuenta["upz"] == ["Tintal Sur"]

    r = cliente.get(f"/api/autoridades/indicador/{cuenta['id']}/evidencia", headers=TOKEN)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    paquete = r.json()
    assert {c["certificado"] for c in paquete["casos"]} == set(certificados)
    assert paquete["casos"][0]["verificacion"].endswith(paquete["casos"][0]["certificado"])
    assert "telefono" not in str(paquete)
    assert cliente.get("/api/autoridades/agrupados").status_code == 401


def test_retroalimentacion(api):
    cliente, _ = api
    h = _reportar(cliente)
    assert cliente.post(f"/api/retroalimentacion/{h}", json={"util": True}).status_code == 200
    assert cliente.post(f"/api/retroalimentacion/{h}", json={}).status_code == 400
    assert cliente.post(f"/api/retroalimentacion/{'0' * 64}", json={"util": True}).status_code == 404
    resumen = cliente.get("/api/autoridades/resumen", headers=TOKEN).json()
    assert resumen["retroalimentacion"]["util_pct"] == 100 and resumen["por_estado"] == {"registrado": 1}


def test_voz(api, monkeypatch):
    cliente, base = api

    async def audio_falso(publico, timeout=None):
        return b"ID3-audio"
    monkeypatch.setattr(verificacion, "audio_de_caso", audio_falso)

    h = _reportar(cliente)
    r = cliente.get(f"/api/voz/{h}.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3-audio"

    # Guion hablado: sin asteriscos ni números o enlaces enmascarados, en trozos que acepta el servicio
    guion = voz.texto_de_caso(base.publico[h])
    assert guion.startswith("Cuidado") and "*" not in guion and "•" not in guion and "[.]" not in guion
    assert all(0 < len(t) <= 190 for t in voz._trozos(guion + " " + "palabra " * 80))

    # "escuchar" en WhatsApp (Twilio) adjunta el audio del último veredicto
    de = {"From": "whatsapp:+573001230000", "NumMedia": "0"}
    cliente.post("/api/whatsapp/webhook", data={**de, "Body": MENSAJE})
    r = cliente.post("/api/whatsapp/webhook", data={**de, "Body": "escuchar"})
    assert "<Media>" in r.text and "/api/voz/" in r.text
