"""
Smoke test de la conexión a Firebase Firestore.

Uso (desde /backend):
    venv\\Scripts\\python scripts\\probar_firebase.py
    # o en Linux/macOS: python scripts/probar_firebase.py

Verifica:
  1. Inicialización con serviceAccountKey.json (o FIREBASE_CREDENTIALS en env).
  2. Escritura, lectura y borrado de un documento de prueba en alertas_bosa.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

# Permite ejecutar el script desde /backend sin instalar el paquete app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.firebase_db import db  # noqa: E402

COLECCION = "alertas_bosa"
DOC_PRUEBA = "_conexion_prueba"


def main() -> int:
    print("1. Conectando a Firestore (escudo-comunitario)…")
    ref = db.collection(COLECCION).document(DOC_PRUEBA)

    print(f"2. Escribiendo documento de prueba en {COLECCION}/{DOC_PRUEBA}…")
    ref.set({
        "mensaje_original": "Documento de prueba de conexión",
        "nivel_riesgo": 0,
        "certificado": "prueba",
        "fecha": datetime.now(timezone.utc).isoformat(),
        "estado": "prueba",
        "canal": "script",
        "flags": [],
        "barrio": "Bosa Centro",
        "lat": 4.6060,
        "lng": -74.1860,
    })

    print("3. Leyendo el documento de vuelta…")
    doc = ref.get()
    if not doc.exists:
        print("   ERROR: el documento no se pudo leer.")
        return 1
    datos = doc.to_dict()
    print(f"   OK: {datos['mensaje_original']} (nivel_riesgo={datos['nivel_riesgo']})")

    print("4. Listando los 5 reportes más recientes de la colección…")
    from firebase_admin import firestore
    recientes = (
        db.collection(COLECCION)
        .order_by("fecha", direction=firestore.Query.DESCENDING)
        .limit(5)
        .stream()
    )
    for d in recientes:
        if d.id == DOC_PRUEBA:
            continue
        m = d.to_dict()
        print(f"   - {d.id}: riesgo {m.get('nivel_riesgo')}% · "
              f"{m.get('barrio')} · {m.get('canal')}")

    print("5. Borrando el documento de prueba…")
    ref.delete()

    print("\n✅ Conexión a Firebase verificada correctamente.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"\n❌ Falló la conexión: {error}")
        print("Revisa que backend/serviceAccountKey.json sea válido y que")
        print("tengas instaladas las dependencias (pip install -r requirements.txt).")
        sys.exit(1)
