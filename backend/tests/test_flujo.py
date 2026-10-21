"""
Flujo completo de la API con una base de datos en memoria (sin Firestore real)
y el LLM en modo heurístico. Las fuentes en red (RDAP, OpenTimestamps) se
sustituyen por dobles para que la prueba sea determinista.

    cd backend && python -m pytest -q tests/test_flujo.py
"""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import firebase_db, procesamiento, registro, verificador


class BaseEnMemoria:
    def __init__(self):
        self.registros, self.privado, self.publico = {}, {}, {}
        self.estado = {"altura": -1, "ultimo_hash": registro.GENESIS}
        self.indicadores, self.conversaciones, self.alertas = {}, {}, {}

    def registrar_reporte(self, *, canal, reportante, mensaje, adjuntos, analisis, privado, publico, fecha=None):
        bloque = registro.construir_bloque(
            altura=self.estado["altura"] + 1, prev=self.estado["ultimo_hash"],
            fecha=fecha or firebase_db.ahora_iso(), canal=canal, reportante=reportante,
            mensaje=mensaje, adjuntos=adjuntos, analisis=analisis)
        h = registro.hash_bloque(bloque)
        self.registros[h] = {**bloque, "hash": h, "anclaje": {"estado": "en_proceso"}}
        self.privado[h] = {**privado, "certificado": h, "reportante": reportante, "fecha": bloque["fecha"]}
        self.publico[h] = {**publico, "certificado": h, "fecha": bloque["fecha"]}
        self.estado = {"altura": bloque["altura"], "ultimo_hash": h}
        return {**bloque, "hash": h}

    def guardar_anclaje(self, h, anclaje):
        self.registros[h]["anclaje"] = anclaje

    def actualizar_ubicacion(self, h, upz, lat, lng, lat_p, lng_p):
        self.publico[h].update({"upz": upz, "lat": lat_p, "lng": lng_p})

    def obtener_bloque(self, h):
        return dict(self.registros[h]) if h in self.registros else None

    def buscar_bloque(self, codigo):
        hits = [b for h, b in self.registros.items() if h.startswith(codigo)]
        return dict(hits[0]) if len(hits) == 1 else None

    def obtener_publico(self, h):
        return self.publico.get(h)

    def bloque_siguiente(self, h):
        return next((dict(b) for b in self.registros.values() if b["prev"] == h), None)

    def bloques_ordenados(self, limite=2000):
        return sorted((dict(b) for b in self.registros.values()), key=lambda b: b["altura"])

    def estado_cadena(self):
        return self.estado

    def consultar_indicadores(self, claves):
        return {c: self.indicadores[c] for c in claves if c in self.indicadores}

    def incrementar_indicadores(self, claves, upz, certificado):
        for c in claves:
            self.indicadores[c] = self.indicadores.get(c, 0) + 1

    def obtener_conversacion(self, u):
        return self.conversaciones.get(u, {})

    def guardar_conversacion(self, u, datos):
        self.conversaciones.setdefault(u, {}).update(datos)

    def reportes_publicos_desde(self, horas):
        return list(self.publico.values())

    def alerta_comunitaria_reciente(self, clave, horas=24):
        return clave in self.alertas

    def guardar_alerta_comunitaria(self, clave, datos):
        self.alertas[clave] = datos


@pytest.fixture
def cliente(monkeypatch):
    base = BaseEnMemoria()
    for nombre in dir(base):
        if not nombre.startswith("_") and hasattr(firebase_db, nombre):
            monkeypatch.setattr(firebase_db, nombre, getattr(base, nombre))
    monkeypatch.setattr(settings, "LLM_PROVIDER", "heuristico")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", None)

    async def ots_falso(h, timeout=None):
        return {"estado": "pendiente_bitcoin", "calendario": "prueba", "prueba_b64": "8BBwcnVlYmE="}
    monkeypatch.setattr(procesamiento, "anclar_opentimestamps", ots_falso)

    async def rdap_falso(client, dominio):
        return {"existe": True, "creado": "2026-10-10", "dias": 11}
    monkeypatch.setattr(verificador, "_rdap", rdap_falso)

    from app.main import app
    return TestClient(app), base


MENSAJE = ("URGENTE: Nequi te informa que tu cuenta será bloqueada hoy. Verifica tu clave en "
           "www.nequi-verificacion-cliente.com y consigna a Nequi 3001234567")


def test_reporte_web_completo(cliente):
    api, base = cliente
    r = api.post("/api/reporte-web", json={"mensaje": MENSAJE, "upz": "Tintal Sur"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nivel"] == "alto" and d["confianza"] > 0
    assert d["tipo_fraude"]["id"] in ("phishing", "suplantacion_entidad")
    assert d["plan_accion"] and d["factores_confianza"]
    fuentes = {f["nombre"] for f in d["verificacion"]["fuentes"]}
    assert "RDAP · registro público de dominios" in fuentes
    assert any("Imita a Nequi" in h["detalle"] for h in d["verificacion"]["hallazgos"])

    # Lo público no contiene datos crudos
    publico = base.publico[d["certificado"]]
    assert "3001234567" not in str(publico) and "mensaje_original" not in publico

    # Certificado verificable y archivos descargables
    v = api.get(f"/api/verificar/{d['certificado'][:16]}").json()
    assert v["integro"] and v["enlaces"]["anterior_valido"]
    # El sello en Bitcoin no hace esperar al ciudadano: se pide después del veredicto
    assert d["anclaje"]["estado"] == "en_proceso"
    assert api.get(f"/api/verificar/{d['certificado']}/prueba.ots").status_code == 404
    assert api.post(f"/api/cadena/sellar/{d['certificado']}").json()["estado"] == "pendiente_bitcoin"
    assert api.get(f"/api/verificar/{d['certificado']}/prueba.ots").status_code == 200
    canon = api.get(f"/api/verificar/{d['certificado']}/registro.json").content
    import hashlib
    assert hashlib.sha256(canon).hexdigest() == d["certificado"]


def test_comunidad_y_auditoria(cliente):
    api, base = cliente
    for _ in range(3):
        d = api.post("/api/reporte-web", json={"mensaje": MENSAJE, "upz": "Tintal Sur"}).json()
    assert any(c["veces"] >= 2 for c in d["comunidad"])
    assert d["alerta_comunitaria"] or base.alertas  # 3 casos del mismo tipo en la UPZ → brote

    assert api.get("/api/cadena/auditoria").json()["valida"]
    # Alguien edita la base de datos a mano para "bajar" un caso
    primero = base.bloques_ordenados()[0]["hash"]
    base.registros[primero]["analisis"]["nivel_riesgo"] = 1
    auditoria = api.get("/api/cadena/auditoria").json()
    assert not auditoria["valida"] and auditoria["errores"][0]["altura"] == 0
    assert api.get(f"/api/verificar/{primero}").json()["integro"] is False


def test_whatsapp_conversacional(cliente):
    api, base = cliente
    r = api.post("/api/whatsapp/webhook", data={"From": "whatsapp:+573001112233", "Body": "hola", "NumMedia": "0"})
    assert "Escudo Comunitario" in r.text

    r = api.post("/api/whatsapp/webhook", data={"From": "whatsapp:+573001112233", "Body": MENSAJE, "NumMedia": "0"})
    assert r.status_code == 200 and "Qué hacer ahora" in r.text and "UPZ" in r.text
    h = next(iter(base.registros))
    assert base.publico[h]["upz"] is None
    assert "3001112233" not in str(base.privado[h])  # el teléfono de la víctima no se guarda
    assert base.registros[h]["anclaje"].get("prueba_b64")  # en WhatsApp se sella en línea

    r = api.post("/api/whatsapp/webhook", data={"From": "whatsapp:+573001112233", "Body": "5", "NumMedia": "0"})
    assert "Tintal Sur" in r.text and base.publico[h]["upz"] == "Tintal Sur"

    r = api.post("/api/whatsapp/webhook", data={"From": "whatsapp:+573001112233", "Body": f"verificar {h[:16]}", "NumMedia": "0"})
    assert "Íntegro" in r.text


def test_firma_twilio_obligatoria(cliente, monkeypatch):
    api, _ = cliente
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "token-de-prueba")
    r = api.post("/api/whatsapp/webhook", data={"From": "whatsapp:+57300", "Body": MENSAJE, "NumMedia": "0"})
    assert r.status_code == 403


def test_simulador_chat_mismo_bot(cliente):
    api, base = cliente
    sesion = {"sesion": "navegador-de-prueba-123"}
    r = api.post("/api/whatsapp/simulador", json={**sesion, "texto": "hola"}).json()
    assert "Escudo Comunitario" in r["mensajes"][0]

    r = api.post("/api/whatsapp/simulador", json={**sesion, "texto": MENSAJE}).json()
    assert len(r["mensajes"]) == 2 and "Qué hacer ahora" in r["mensajes"][0]
    assert r["opciones"] and r["certificado"]
    assert base.registros[r["certificado"]]["canal"] == "chat"

    # Ubicación del navegador dentro de Bosa completa el reporte
    r2 = api.post("/api/whatsapp/simulador", json={**sesion, "lat": 4.6060, "lng": -74.1860}).json()
    assert "UPZ" in r2["mensajes"][0] and base.publico[r["certificado"]]["upz"]
