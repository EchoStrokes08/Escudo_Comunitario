"""
Backend local con base de datos EN MEMORIA (no toca Firestore).

Útil para ensayar la demo o desarrollar sin ensuciar la cadena real de
certificados. La IA y las fuentes abiertas (RDAP, OpenTimestamps) sí son reales.

    cd backend
    python scripts/servidor_demo.py          # http://localhost:8000
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import uvicorn  # noqa: E402

from app.services import firebase_db  # noqa: E402
from test_flujo import BaseEnMemoria  # noqa: E402

base = BaseEnMemoria()
for nombre in dir(base):
    if not nombre.startswith("_") and hasattr(firebase_db, nombre):
        setattr(firebase_db, nombre, getattr(base, nombre))

if __name__ == "__main__":
    from app.main import app
    print("AVISO: base de datos EN MEMORIA: los reportes se pierden al cerrar el servidor.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
