# 🛡️ Escudo Comunitario — Bosa

Ecosistema de prevención de fraude digital para la Localidad de Bosa (Hackathon Colombia 5.0).

## Capacidades

| Capacidad | Implementación |
|---|---|
| Detección con IA | `backend/app/services/analizador.py` — integración real con Google Gemini u OpenAI (JSON: `nivel_riesgo` 0-100 + `flags`), con fallback heurístico local |
| Verificación en fuentes abiertas | `backend/app/services/verificador.py` — extrae URLs, dominios y números de cuenta y los cruza contra listas de dominios maliciosos y reportes del CAI Virtual (mock) |
| Registro inmanipulable | `backend/app/services/certificado.py` — hash SHA-256 completo, verificable con `verificar_integridad()` |
| Canal accesible | `frontend/src/pages/Reportar.jsx` (web) + `backend/app/api/whatsapp.py` (webhook Twilio con TwiML XML) |
| Inteligencia territorial | `frontend/src/pages/Dashboard.jsx` + `frontend/src/components/MapaCalor.jsx` — mapa de calor react-leaflet con datos en tiempo real desde Firestore |

## Arquitectura

```
backend/                  FastAPI (serverless en Vercel)
  app/main.py             App + middleware CORS (configurable por CORS_ORIGINS)
  app/api/whatsapp.py     POST /api/whatsapp/webhook (Twilio)
  app/api/web_report.py   POST /api/reporte-web (formulario React)
  app/services/           analizador · verificador · certificado · firebase_db · geolocalizacion
  app/core/config.py      Lectura de variables de entorno (.env)
frontend/                 React + Vite (SPA en Vercel)
  src/pages/              Dashboard (/) · Reportar (/reportar)
  src/components/         MapaCalor.jsx (react-leaflet)
  src/services/firebase.js
```

## Configuración

1. **Backend**
   ```bash
   cd backend
   cp .env.example .env       # completa Twilio, Firebase y GEMINI_API_KEY
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
2. **Frontend**
   ```bash
   cd frontend
   cp .env.example .env       # VITE_API_URL y credenciales públicas de Firebase
   npm install
   npm run dev
   ```

> 🔒 Los archivos `.env`, `serviceAccountKey.json` y credenciales están excluidos del repo por `.gitignore`. En Vercel, configura las mismas variables en *Project → Settings → Environment Variables*.

## Endpoints

- `GET /` — health check
- `POST /api/whatsapp/webhook` — recibe mensajes de Twilio, responde con TwiML XML
- `POST /api/reporte-web` — `{ mensaje, barrio?, lat?, lng? }` → veredicto IA + cruce de fuentes + certificado SHA-256
