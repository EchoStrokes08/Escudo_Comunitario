"""
Publica firestore.rules en el proyecto usando la cuenta de servicio
(no requiere instalar Firebase CLI).

    cd backend
    python scripts/desplegar_reglas.py            # muestra las reglas y pide confirmación
    python scripts/desplegar_reglas.py --si       # publica sin preguntar

IMPORTANTE: córrelo DESPUÉS de desplegar la nueva versión del frontend
(que lee panel_publico). Si se cierra alertas_bosa antes, el panel anterior
queda sin datos.
"""
import sys
from pathlib import Path

import google.auth.transport.requests
from google.oauth2 import service_account

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ALCANCES = ["https://www.googleapis.com/auth/firebase", "https://www.googleapis.com/auth/cloud-platform"]


def main():
    if not settings.FIREBASE_CREDENTIALS_DICT:
        sys.exit("No se encontró la cuenta de servicio (FIREBASE_CREDENTIALS o serviceAccountKey.json).")
    proyecto = settings.FIREBASE_CREDENTIALS_DICT["project_id"]
    reglas = (RAIZ / "firestore.rules").read_text(encoding="utf-8")

    print(f"Proyecto: {proyecto}\n{'-' * 60}\n{reglas}\n{'-' * 60}")
    if "--si" not in sys.argv and input("¿Publicar estas reglas? (s/N): ").strip().lower() != "s":
        sys.exit("Cancelado.")

    cred = service_account.Credentials.from_service_account_info(settings.FIREBASE_CREDENTIALS_DICT, scopes=ALCANCES)
    sesion = google.auth.transport.requests.AuthorizedSession(cred)
    base = f"https://firebaserules.googleapis.com/v1/projects/{proyecto}"

    r = sesion.post(f"{base}/rulesets", json={"source": {"files": [{"name": "firestore.rules", "content": reglas}]}})
    r.raise_for_status()
    ruleset = r.json()["name"]

    release = f"projects/{proyecto}/releases/cloud.firestore"
    r = sesion.patch(f"{base}/releases/cloud.firestore", json={"release": {"name": release, "rulesetName": ruleset}})
    if r.status_code == 404:
        r = sesion.post(f"{base}/releases", json={"name": release, "rulesetName": ruleset})
    r.raise_for_status()
    print(f"OK: reglas publicadas ({ruleset}).")


if __name__ == "__main__":
    main()
