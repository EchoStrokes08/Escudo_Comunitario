import os
import json
from dotenv import load_dotenv

load_dotenv()

class Settings:
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    
    # Intenta leer el JSON desde la variable de entorno (Vercel) o usa fallback
    firebase_env = os.getenv("FIREBASE_CREDENTIALS")
    if firebase_env:
        FIREBASE_CREDENTIALS_DICT = json.loads(firebase_env)
    else:
        FIREBASE_CREDENTIALS_DICT = None

settings = Settings()