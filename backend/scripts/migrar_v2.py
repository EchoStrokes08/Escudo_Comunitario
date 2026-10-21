"""
Migra los reportes antiguos de alertas_bosa al esquema v2:

  - Cada reporte antiguo entra a la cadena de certificados (en orden de fecha,
    conservando su fecha original) y recibe un certificado verificable nuevo.
  - Se crea su versión anonimizada en panel_publico.
  - El teléfono se reemplaza por su seudónimo en el registro nuevo.
  - El documento antiguo se marca con 'migrado_a' (idempotente: se puede correr
    varias veces). Con --borrar-legado se elimina, porque guardaba el teléfono en claro.

    cd backend
    python scripts/migrar_v2.py                 # simulación: muestra qué haría
    python scripts/migrar_v2.py --aplicar
    python scripts/migrar_v2.py --aplicar --borrar-legado
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.riesgo import nivel  # noqa: E402
from app.services import firebase_db  # noqa: E402
from app.services.analizador import analisis_heuristico  # noqa: E402
from app.services.anonimizar import anonimizar_texto, generalizar_ubicacion, seudonimo  # noqa: E402
from app.services.registro import anclar_opentimestamps  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _legado() -> list[tuple[str, dict]]:
    docs = firebase_db.obtener_db().collection(firebase_db.COL_PRIVADA).stream()
    pendientes = [(d.id, d.to_dict()) for d in docs if d.id != "_conexion_prueba"]
    pendientes = [(i, d) for i, d in pendientes if "altura" not in d and not d.get("migrado_a")]
    return sorted(pendientes, key=lambda par: str(par[1].get("fecha", "")))


async def main():
    aplicar = "--aplicar" in sys.argv
    borrar = "--borrar-legado" in sys.argv
    pendientes = _legado()
    print(f"Reportes antiguos por migrar: {len(pendientes)}  ({'APLICANDO' if aplicar else 'simulación'})")

    for doc_id, d in pendientes:
        mensaje = d.get("mensaje_original") or d.get("mensaje") or ""
        riesgo = int(d.get("nivel_riesgo") or 0)
        heur = analisis_heuristico(mensaje)
        tipo = heur["tipo_fraude"] if riesgo >= 25 else "legitimo"
        if tipo == "legitimo" and riesgo >= 40:
            tipo = "otro"
        motor = d.get("motor") or "heuristico"
        confianza = 55 if motor == "llm" else 30
        canal = d.get("canal") or "web"
        reportante = seudonimo(d.get("telefono")) if canal == "whatsapp" else "anonimo"
        upz = d.get("upz") or d.get("barrio")
        lat, lng = d.get("lat"), d.get("lng")
        flags = list(d.get("flags") or [])
        adjuntos = [a for a in (d.get("adjuntos") or []) if a.get("sha256")]
        fecha = str(d.get("fecha") or firebase_db.ahora_iso())

        print(f"  {fecha[:19]}  {canal:8}  riesgo {riesgo:3}  {tipo:22}  {anonimizar_texto(mensaje, 60)}")
        if not aplicar:
            continue

        lat_pub, lng_pub = generalizar_ubicacion(lat, lng) if canal == "web" else (None, None)
        privado = {
            "mensaje_original": mensaje, "texto_detectado": "", "nivel_riesgo": riesgo, "confianza": confianza,
            "tipo_fraude": tipo, "entidad_suplantada": "", "flags": flags, "resumen": d.get("resumen", ""),
            "verificacion": d.get("verificacion") or {}, "indicadores": [], "motor": motor, "modelo": None,
            "upz": upz, "lat": lat, "lng": lng, "adjuntos": adjuntos, "estado": "migrado",
            "certificado_legado": d.get("certificado"), "id_legado": doc_id,
        }
        publico = {
            "mensaje_anonimizado": anonimizar_texto(mensaje), "nivel_riesgo": riesgo, "confianza": confianza,
            "tipo_fraude": tipo, "entidad_suplantada": "", "flags": flags,
            "resumen": anonimizar_texto(d.get("resumen", ""), 400), "hallazgos": [], "indicadores": [],
            "comunidad": [], "upz": upz if canal == "web" else None, "lat": lat_pub, "lng": lng_pub,
            "adjuntos": len(adjuntos), "con_audio": False, "motor": "ia" if motor == "llm" else "local",
            "anclaje": "en_proceso", "migrado": True,
        }
        bloque = firebase_db.registrar_reporte(
            canal=canal, reportante=reportante, mensaje=mensaje, adjuntos=adjuntos,
            analisis={"nivel_riesgo": riesgo, "confianza": confianza, "tipo_fraude": tipo, "flags": flags, "motor": motor},
            privado=privado, publico=publico, fecha=fecha,
        )
        firebase_db.guardar_anclaje(bloque["hash"], await anclar_opentimestamps(bloque["hash"]))

        ref = firebase_db.obtener_db().collection(firebase_db.COL_PRIVADA).document(doc_id)
        if borrar:
            ref.delete()
        else:
            ref.update({"migrado_a": bloque["hash"]})
        print(f"      → bloque #{bloque['altura']}  {bloque['hash'][:16]}…  ({nivel(riesgo)})")

    if not aplicar:
        print("\nNada se modificó. Corre con --aplicar para migrar.")


if __name__ == "__main__":
    asyncio.run(main())
