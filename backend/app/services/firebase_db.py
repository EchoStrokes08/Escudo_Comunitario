"""
Persistencia en Firestore.

Colecciones:
  alertas_bosa/{hash}          PRIVADA (solo backend): caso completo para autoridades.
                               Nunca guarda el teléfono, solo su seudónimo.
  panel_publico/{hash}         PÚBLICA (solo lectura): versión anonimizada para el panel.
  registros/{hash}             PÚBLICA (solo lectura): bloques de la cadena de hashes.
  cadena/estado                PRIVADA: altura y último hash (se actualiza en transacción).
  indicadores/{id}             PRIVADA: veces que se reportó cada dominio/cuenta/teléfono.
  conversaciones/{seudonimo}   PRIVADA: estado de la conversación de WhatsApp.
  alertas_comunitarias/{id}    PÚBLICA (solo lectura): brotes detectados por UPZ.
  suscriptores_alertas/{id}    PRIVADA: líderes que reciben las alertas (Telegram / WhatsApp).
  avisos_caso/{id}             PRIVADA: quién pidió ("avísame") recibir los avances de su caso.
                               Única excepción al "sin teléfono": consentimiento explícito, y se
                               borra al cerrar el caso.
  retroalimentacion/{id}       PRIVADA: "¿te sirvió?" / "era legítimo" de cada veredicto.

El backend usa la cuenta de servicio (Admin SDK), que no está sujeta a las
reglas de Firestore; el navegador solo puede leer las colecciones públicas.
"""
import hashlib
import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Increment, ArrayUnion, Query, transactional

from app.core.config import settings
from app.services.registro import GENESIS, construir_bloque, construir_seguimiento, hash_bloque

COL_PRIVADA = "alertas_bosa"
COL_PUBLICA = "panel_publico"
COL_REGISTROS = "registros"
COL_INDICADORES = "indicadores"
COL_CONVERSACIONES = "conversaciones"
COL_ALERTAS_COMUNIDAD = "alertas_comunitarias"
COL_SUSCRIPTORES = "suscriptores_alertas"
COL_RETROALIMENTACION = "retroalimentacion"
COL_AVISOS_CASO = "avisos_caso"


@lru_cache(maxsize=1)
def obtener_db():
    # Evitar doble inicialización en Vercel / serverless / recargas de Uvicorn
    if not firebase_admin._apps:
        if settings.FIREBASE_CREDENTIALS_DICT:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_DICT)
        else:
            posibles_rutas = [
                Path("backend/serviceAccountKey.json"),
                Path("serviceAccountKey.json"),
                Path(__file__).resolve().parent.parent.parent / "serviceAccountKey.json",
            ]
            ruta = next((p for p in posibles_rutas if p.exists()), None)
            if ruta:
                cred = credentials.Certificate(str(ruta))
            elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")).exists():
                cred = credentials.Certificate(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            else:
                cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    return firestore.client()


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# Registro del reporte (cadena + privado + público, en una sola transacción)
# --------------------------------------------------------------------------- #

def registrar_reporte(*, canal: str, reportante: str, mensaje: str, adjuntos: list[dict],
                      analisis: dict, privado: dict, publico: dict, fecha: str | None = None) -> dict:
    """
    Crea el bloque encadenado y guarda las versiones privada y pública del caso
    de forma atómica. Retorna el bloque con su 'hash'.
    """
    db = obtener_db()
    ref_estado = db.collection("cadena").document("estado")
    fecha = fecha or ahora_iso()

    @transactional
    def _txn(transaction):
        snap = ref_estado.get(transaction=transaction)
        estado = snap.to_dict() if snap.exists else {"altura": -1, "ultimo_hash": GENESIS}
        bloque = construir_bloque(
            altura=estado["altura"] + 1, prev=estado["ultimo_hash"], fecha=fecha, canal=canal,
            reportante=reportante, mensaje=mensaje, adjuntos=adjuntos, analisis=analisis,
        )
        h = hash_bloque(bloque)
        base = {"certificado": h, "altura": bloque["altura"], "fecha": fecha, "canal": canal}
        transaction.set(db.collection(COL_REGISTROS).document(h),
                        {**bloque, "hash": h, "anclaje": {"estado": "en_proceso"}})
        transaction.set(db.collection(COL_PRIVADA).document(h), {**privado, **base, "reportante": reportante})
        transaction.set(db.collection(COL_PUBLICA).document(h), {**publico, **base})
        transaction.set(ref_estado, {"altura": bloque["altura"], "ultimo_hash": h, "actualizado": fecha})
        return {**bloque, "hash": h}

    return _txn(db.transaction())


def registrar_seguimiento(*, caso: str, estado: str, actor: str, nota: str) -> dict:
    """
    Agrega a la cadena un bloque de seguimiento (cambio de estado del caso) y
    actualiza el estado en las versiones privada y pública, en una transacción.
    """
    db = obtener_db()
    ref_estado = db.collection("cadena").document("estado")
    fecha = ahora_iso()

    @transactional
    def _txn(transaction):
        snap = ref_estado.get(transaction=transaction)
        cadena = snap.to_dict() if snap.exists else {"altura": -1, "ultimo_hash": GENESIS}
        bloque = construir_seguimiento(altura=cadena["altura"] + 1, prev=cadena["ultimo_hash"], fecha=fecha,
                                       caso=caso, estado=estado, actor=actor, nota=nota)
        h = hash_bloque(bloque)
        transaction.set(db.collection(COL_REGISTROS).document(h),
                        {**bloque, "hash": h, "nota": nota, "anclaje": {"estado": "en_proceso"}})
        cambio = {"estado": estado, "estado_fecha": fecha, "estado_actor": actor, "estado_nota": nota}
        transaction.update(db.collection(COL_PRIVADA).document(caso), cambio)
        transaction.update(db.collection(COL_PUBLICA).document(caso), cambio)
        transaction.set(ref_estado, {"altura": bloque["altura"], "ultimo_hash": h, "actualizado": fecha})
        return {**bloque, "hash": h, "nota": nota}

    return _txn(db.transaction())


def seguimientos_de(caso: str) -> list[dict]:
    """Bloques de seguimiento de un caso, en orden (se ordena aquí para no requerir índice compuesto)."""
    docs = obtener_db().collection(COL_REGISTROS).where("caso", "==", caso).limit(100).stream()
    return sorted(({**d.to_dict(), "hash": d.id} for d in docs), key=lambda b: b["altura"])


def obtener_privado(h: str) -> dict | None:
    snap = obtener_db().collection(COL_PRIVADA).document(h).get()
    return snap.to_dict() if snap.exists else None


def suscribir_avisos_caso(caso: str, canal: str, destino: str):
    doc = hashlib.sha256(f"{caso}:{canal}:{destino}".encode()).hexdigest()[:40]
    obtener_db().collection(COL_AVISOS_CASO).document(doc).set(
        {"caso": caso, "canal": canal, "destino": destino, "fecha": ahora_iso()})


def avisos_caso(caso: str) -> list[dict]:
    return [d.to_dict() for d in obtener_db().collection(COL_AVISOS_CASO).where("caso", "==", caso).limit(20).stream()]


def borrar_avisos_caso(caso: str):
    db = obtener_db()
    lote = db.batch()
    for d in db.collection(COL_AVISOS_CASO).where("caso", "==", caso).limit(50).stream():
        lote.delete(d.reference)
    lote.commit()


def guardar_anclaje(h: str, anclaje: dict):
    """El anclaje no forma parte del hash: se puede completar después sin romper la cadena."""
    datos = {**anclaje, "fecha": ahora_iso()}
    db = obtener_db()
    db.collection(COL_REGISTROS).document(h).update({"anclaje": datos})
    publico = db.collection(COL_PUBLICA).document(h)
    if publico.get().exists:  # los bloques de seguimiento no tienen versión pública propia
        publico.update({"anclaje": datos.get("estado")})


def actualizar_ubicacion(h: str, upz: str | None, lat: float | None, lng: float | None,
                         lat_publica: float | None, lng_publica: float | None):
    """La ubicación es metadato del panel (no entra al hash): se puede completar después."""
    db = obtener_db()
    db.collection(COL_PRIVADA).document(h).update({"upz": upz, "lat": lat, "lng": lng})
    db.collection(COL_PUBLICA).document(h).update({"upz": upz, "lat": lat_publica, "lng": lng_publica})


# --------------------------------------------------------------------------- #
# Cadena: consulta y auditoría
# --------------------------------------------------------------------------- #

def obtener_bloque(h: str) -> dict | None:
    snap = obtener_db().collection(COL_REGISTROS).document(h).get()
    if not snap.exists:
        return None
    # El hash válido es el id del documento (si alguien edita el campo 'hash', no cambia el id)
    return {**snap.to_dict(), "hash": snap.id}


def buscar_bloque(codigo: str) -> dict | None:
    """Acepta el hash completo o un prefijo único (los 16 caracteres que muestra WhatsApp)."""
    codigo = codigo.lower()
    if len(codigo) == 64:
        return obtener_bloque(codigo)
    docs = list(obtener_db().collection(COL_REGISTROS)
                .where("hash", ">=", codigo).where("hash", "<", codigo + "g").limit(2).stream())
    if len(docs) != 1:
        return None
    return {**docs[0].to_dict(), "hash": docs[0].id}


def obtener_publico(h: str) -> dict | None:
    snap = obtener_db().collection(COL_PUBLICA).document(h).get()
    return snap.to_dict() if snap.exists else None


def bloque_siguiente(h: str) -> dict | None:
    docs = obtener_db().collection(COL_REGISTROS).where("prev", "==", h).limit(1).stream()
    for d in docs:
        return {**d.to_dict(), "hash": d.id}
    return None


def bloques_ordenados(limite: int = 2000) -> list[dict]:
    docs = obtener_db().collection(COL_REGISTROS).order_by("altura").limit(limite).stream()
    return [{**d.to_dict(), "hash": d.id} for d in docs]


def estado_cadena() -> dict:
    snap = obtener_db().collection("cadena").document("estado").get()
    return snap.to_dict() if snap.exists else {"altura": -1, "ultimo_hash": GENESIS}


def bloques_sin_anclar(limite: int = 50) -> list[str]:
    docs = (obtener_db().collection(COL_REGISTROS)
            .where("anclaje.estado", "in", ["sin_anclar", "en_proceso"]).limit(limite).stream())
    return [d.id for d in docs]


# --------------------------------------------------------------------------- #
# Indicadores comunitarios (dominios, cuentas, teléfonos de estafadores)
# --------------------------------------------------------------------------- #

def _id_indicador(tipo: str, valor: str) -> str:
    return hashlib.sha256(f"{tipo}:{valor}".encode()).hexdigest()[:40]


def consultar_indicadores(claves: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    if not claves:
        return {}
    db = obtener_db()
    refs = {(t, v): db.collection(COL_INDICADORES).document(_id_indicador(t, v)) for t, v in claves}
    veces = {}
    for snap in db.get_all(list(refs.values())):
        if snap.exists:
            datos = snap.to_dict()
            veces[(datos["tipo"], datos["valor"])] = int(datos.get("veces", 0))
    return veces


def incrementar_indicadores(claves: list[tuple[str, str]], upz: str | None, certificado: str):
    if not claves:
        return
    db = obtener_db()
    lote = db.batch()
    fecha = ahora_iso()
    for tipo, valor in claves:
        ref = db.collection(COL_INDICADORES).document(_id_indicador(tipo, valor))
        # Sin UPZ (reportes de chat) no se anota zona: ubicar_indicadores la agrega cuando llega
        lote.set(ref, {
            "tipo": tipo, "valor": valor, "veces": Increment(1), "ultima": fecha,
            "upz": ArrayUnion([upz] if upz else []), "certificados": ArrayUnion([certificado]),
        }, merge=True)
    lote.commit()


def indicadores_reincidentes(minimo: int = 2, limite: int = 100) -> list[dict]:
    """Dominios, cuentas y teléfonos reportados por varias personas: un caso con varias víctimas."""
    docs = (obtener_db().collection(COL_INDICADORES).where("veces", ">=", minimo)
            .order_by("veces", direction=Query.DESCENDING).limit(limite).stream())
    return [{"id": d.id, **d.to_dict()} for d in docs]


def obtener_indicador(id_indicador: str) -> dict | None:
    snap = obtener_db().collection(COL_INDICADORES).document(id_indicador).get()
    return {"id": snap.id, **snap.to_dict()} if snap.exists else None


def casos_por_certificados(certificados: list[str]) -> list[dict]:
    if not certificados:
        return []
    db = obtener_db()
    refs = [db.collection(COL_PRIVADA).document(h) for h in certificados[:200]]
    return [{"id": s.id, **s.to_dict()} for s in db.get_all(refs) if s.exists]


def ubicar_indicadores(certificado: str, upz: str):
    """Agrega la UPZ, respondida después en el chat, a los indicadores del reporte."""
    db = obtener_db()
    snap = db.collection(COL_PRIVADA).document(certificado).get()
    claves = [(i["tipo"], i["valor"]) for i in (snap.to_dict() or {}).get("indicadores", [])] if snap.exists else []
    if not claves:
        return
    lote = db.batch()
    for tipo, valor in claves:
        ref = db.collection(COL_INDICADORES).document(_id_indicador(tipo, valor))
        lote.set(ref, {"tipo": tipo, "valor": valor, "upz": ArrayUnion([upz])}, merge=True)
    lote.commit()


# --------------------------------------------------------------------------- #
# Conversaciones de WhatsApp
# --------------------------------------------------------------------------- #

def obtener_conversacion(seudonimo: str) -> dict:
    snap = obtener_db().collection(COL_CONVERSACIONES).document(seudonimo).get()
    return snap.to_dict() if snap.exists else {}


def guardar_conversacion(seudonimo: str, datos: dict):
    obtener_db().collection(COL_CONVERSACIONES).document(seudonimo).set(
        {**datos, "actualizado": ahora_iso()}, merge=True)


# --------------------------------------------------------------------------- #
# Brotes y alertas comunitarias
# --------------------------------------------------------------------------- #

def reportes_publicos_desde(horas: int) -> list[dict]:
    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    docs = obtener_db().collection(COL_PUBLICA).where("fecha", ">=", desde).limit(1000).stream()
    return [{**d.to_dict(), "id": d.id} for d in docs]


def alerta_comunitaria_reciente(clave: str, horas: int = 24) -> bool:
    snap = obtener_db().collection(COL_ALERTAS_COMUNIDAD).document(clave).get()
    if not snap.exists:
        return False
    fecha = snap.to_dict().get("fecha", "")
    try:
        emitida = datetime.fromisoformat(fecha.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - emitida < timedelta(hours=horas)


def guardar_alerta_comunitaria(clave: str, datos: dict):
    obtener_db().collection(COL_ALERTAS_COMUNIDAD).document(clave).set({**datos, "fecha": ahora_iso()})


def suscribir_lider(canal: str, destino: str, nombre: str = ""):
    """Líder comunitario que recibe alertas tempranas (canal: 'telegram' | 'whatsapp_meta')."""
    obtener_db().collection(COL_SUSCRIPTORES).document(f"{canal}-{destino}").set(
        {"canal": canal, "destino": destino, "nombre": nombre[:80], "fecha": ahora_iso()})


def desuscribir_lider(canal: str, destino: str):
    obtener_db().collection(COL_SUSCRIPTORES).document(f"{canal}-{destino}").delete()


def lideres_suscritos() -> list[dict]:
    return [d.to_dict() for d in obtener_db().collection(COL_SUSCRIPTORES).limit(200).stream()]


# --------------------------------------------------------------------------- #
# Retroalimentación de las personas ("¿te sirvió?", "era legítimo")
# --------------------------------------------------------------------------- #

def guardar_retroalimentacion(certificado: str, origen: str, util: bool | None, era_legitimo: bool | None):
    """Una opinión por persona y certificado (la última reemplaza a la anterior)."""
    doc = hashlib.sha256(f"{certificado}:{origen}".encode()).hexdigest()[:40]
    obtener_db().collection(COL_RETROALIMENTACION).document(doc).set({
        "certificado": certificado, "util": util, "era_legitimo": era_legitimo, "fecha": ahora_iso(),
    })


def retroalimentaciones(limite: int = 2000) -> list[dict]:
    return [d.to_dict() for d in obtener_db().collection(COL_RETROALIMENTACION).limit(limite).stream()]


# --------------------------------------------------------------------------- #
# Autoridades
# --------------------------------------------------------------------------- #

def casos_completos(limite: int = 500) -> list[dict]:
    docs = (obtener_db().collection(COL_PRIVADA)
            .order_by("fecha", direction=Query.DESCENDING).limit(limite).stream())
    return [{"id": d.id, **d.to_dict()} for d in docs]
