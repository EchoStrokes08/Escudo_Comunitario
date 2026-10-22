"""
Configura el bot de Telegram: webhook (con secreto), comandos y descripción.

    cd backend
    python scripts/configurar_telegram.py <TOKEN_DEL_BOT> [URL_PUBLICA]

URL_PUBLICA por defecto: APP_URL (https://escudocomunitario.vercel.app).
El mismo TELEGRAM_BOT_TOKEN debe estar en las variables de entorno de Vercel:
el secreto del webhook se deriva de él en ambos lados.
"""
import hashlib
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402

COMANDOS = [
    {"command": "start", "description": "Cómo usar el Escudo Comunitario"},
    {"command": "verificar", "description": "Comprobar un certificado: /verificar <código>"},
    {"command": "estado", "description": "Ver cómo avanza tu caso: /estado [código]"},
    {"command": "escuchar", "description": "Escuchar el resultado de tu último reporte"},
    {"command": "seguimiento", "description": "Recibir aquí los avances de tu caso"},
    {"command": "alertas", "description": "Recibir alertas tempranas de fraude en Bosa (líderes)"},
    {"command": "cancelar", "description": "Dejar de recibir alertas"},
]
DESCRIPCION = ("Escudo Comunitario de Bosa: reenvíame un mensaje sospechoso, una captura o una nota de voz y te digo "
               "si es fraude, qué hacer y te entrego un certificado verificable. Gratis y anónimo.")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    token = sys.argv[1].strip()
    url = (sys.argv[2] if len(sys.argv) > 2 else settings.APP_URL).rstrip("/") + "/api/telegram/webhook"
    secreto = hashlib.sha256(f"escudo:{token}".encode()).hexdigest()[:40]
    api = f"https://api.telegram.org/bot{token}"

    with httpx.Client(timeout=20) as client:
        yo = client.get(f"{api}/getMe").json()
        if not yo.get("ok"):
            sys.exit(f"Token inválido: {yo}")
        print(f"Bot: @{yo['result']['username']}")
        pasos = {
            "setWebhook": {"url": url, "secret_token": secreto, "drop_pending_updates": True,
                           "allowed_updates": ["message", "edited_message"]},
            "setMyCommands": {"commands": COMANDOS},
            "setMyDescription": {"description": DESCRIPCION},
            "setMyShortDescription": {"short_description": "¿Te llegó un mensaje raro? Te digo si es fraude."},
        }
        for metodo, cuerpo in pasos.items():
            r = client.post(f"{api}/{metodo}", json=cuerpo).json()
            print(f"{metodo}: {'OK' if r.get('ok') else r}")
        info = client.get(f"{api}/getWebhookInfo").json()["result"]
        print(f"Webhook: {info.get('url')}  pendientes={info.get('pending_update_count')}  "
              f"último error={info.get('last_error_message') or 'ninguno'}")
        print(f"Abre el bot: https://t.me/{yo['result']['username']}")


if __name__ == "__main__":
    main()
