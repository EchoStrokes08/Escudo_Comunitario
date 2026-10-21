"""
Punto de entrada de Vercel: expone la app FastAPI de backend/ como función serverless.
Vercel enruta /api/* aquí (ver vercel.json en la raíz) y FastAPI recibe la ruta original.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
