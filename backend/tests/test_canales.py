"""
Canales gratuitos de mensajería (Telegram y WhatsApp de Meta) con la API de cada
plataforma simulada: se capturan los mensajes que el bot enviaría.
"""
import pytest

from app.api import telegram, whatsapp_meta
from app.core.config import settings
from app.services import alertas_comunitarias

from test_flujo import MENSAJE, cliente  # noqa: F401  (fixture compartida)


@pytest.fixture
def enviados(monkeypatch, cliente):  # noqa: F811
    salida = []

    async def telegram_falso(chat_id, texto, opciones=None, pedir_ubicacion=False):
        salida.append(("telegram", str(chat_id), texto, opciones))
        return True

    async def meta_falso(numero, texto, opciones=None):
        salida.append(("whatsapp_meta", numero, texto, opciones))
        return True

    async def nada(*_a, **_k):
        return None

    for modulo in (telegram, alertas_comunitarias):
        monkeypatch.setattr(modulo, "enviar_telegram", telegram_falso)
    for modulo in (whatsapp_meta, alertas_comunitarias):
        monkeypatch.setattr(modulo, "enviar_whatsapp_meta", meta_falso)
    monkeypatch.setattr(telegram, "accion_telegram", nada)
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "123:prueba")
    monkeypatch.setattr(settings, "TELEGRAM_WEBHOOK_SECRET", "secreto")
    monkeypatch.setattr(settings, "META_WHATSAPP_TOKEN", "token")
    monkeypatch.setattr(settings, "META_PHONE_NUMBER_ID", "999")
    return salida


def _telegram(api, texto=None, **extra):
    mensaje = {"chat": {"id": 555}, "from": {"first_name": "Marta"}, **extra}
    if texto is not None:
        mensaje["text"] = texto
    return api.post("/api/telegram/webhook", json={"update_id": 1, "message": mensaje},
                    headers={"X-Telegram-Bot-Api-Secret-Token": "secreto"})


def test_telegram_conversacion_completa(cliente, enviados):  # noqa: F811
    api, base = cliente
    assert _telegram(api, "/start").status_code == 200
    assert "Escudo Comunitario" in enviados[-1][2]

    _telegram(api, MENSAJE)
    veredicto, pregunta = enviados[-2], enviados[-1]
    assert "Qué hacer ahora" in veredicto[2] and pregunta[3]  # la pregunta lleva los botones de UPZ
    h = next(iter(base.registros))
    assert base.registros[h]["canal"] == "telegram" and base.registros[h]["anclaje"].get("prueba_b64")

    _telegram(api, "5. Tintal Sur")  # botón del teclado
    assert base.publico[h]["upz"] == "Tintal Sur"


def test_telegram_rechaza_secreto_invalido(cliente, enviados):  # noqa: F811
    api, _ = cliente
    r = api.post("/api/telegram/webhook", json={"message": {"chat": {"id": 1}, "text": MENSAJE}},
                 headers={"X-Telegram-Bot-Api-Secret-Token": "otro"})
    assert r.status_code == 403


def test_lider_suscrito_recibe_alerta_de_brote(cliente, enviados):  # noqa: F811
    api, base = cliente
    _telegram(api, "/alertas")
    assert base.lideres and "alertas tempranas" in enviados[-1][2]
    for _ in range(3):
        api.post("/api/reporte-web", json={"mensaje": MENSAJE, "upz": "Tintal Sur"})
    alertas = [e for e in enviados if "Alerta temprana" in e[2]]
    assert alertas and alertas[0][1] == "555"
    assert next(iter(base.alertas.values()))["lideres_notificados"] >= 1


def test_reportes_del_chat_ubicados_despues_disparan_brote(cliente, enviados):  # noqa: F811
    api, base = cliente
    _telegram(api, "/alertas")
    for _ in range(3):
        _telegram(api, MENSAJE)  # el chat registra el reporte sin UPZ...
        assert not base.alertas
        _telegram(api, "5. Tintal Sur")  # ...y la UPZ llega en el turno siguiente
    assert [e for e in enviados if "Alerta temprana" in e[2]]
    assert next(iter(base.alertas.values()))["upz"] == "Tintal Sur"


def test_whatsapp_meta_verificacion_y_mensajes(cliente, enviados):  # noqa: F811
    api, base = cliente
    r = api.get("/api/whatsapp-meta/webhook", params={"hub.mode": "subscribe",
                                                      "hub.verify_token": settings.META_VERIFY_TOKEN,
                                                      "hub.challenge": "1234"})
    assert r.text == "1234"
    assert api.get("/api/whatsapp-meta/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                                         "hub.challenge": "1"}).status_code == 403

    def evento(mensaje):
        return {"entry": [{"changes": [{"value": {"messages": [{"from": "573001112233", **mensaje}]}}]}]}

    api.post("/api/whatsapp-meta/webhook", json=evento({"type": "text", "text": {"body": MENSAJE}}))
    assert "Qué hacer ahora" in enviados[-2][2] and enviados[-1][3]  # lista de UPZ
    h = next(iter(base.registros))
    assert "3001112233" not in str(base.privado[h])

    api.post("/api/whatsapp-meta/webhook", json=evento({"type": "interactive",
                                                       "interactive": {"list_reply": {"id": "3"}}}))
    assert base.publico[h]["upz"] == "Bosa Central"
