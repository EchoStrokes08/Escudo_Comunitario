# 🛡️ Escudo Comunitario — Bosa

Ecosistema de prevención de fraude digital para la Localidad de Bosa (Hackathon Colombia 5.0).

## Capacidades

| Capacidad | Implementación |
|---|---|
| Detección con IA | `backend/app/services/analizador.py` — agente multimodal (Gemini 1.5 Flash principal, GPT-4o respaldo): texto + imágenes (OCR visual de capturas) + PDFs (facturas falsas), con `nivel_riesgo` 0-100 + `flags` y fallback heurístico local |
| Soporte de archivos | `backend/app/services/archivos.py` — validación MIME + magic bytes + peso (env `MAX_PESO_MB`/`MAX_ARCHIVOS`), Base64 inline al LLM, extracción de texto con `pypdf` |
| Verificación en fuentes abiertas | `backend/app/services/verificador.py` — extrae URLs, dominios y números de cuenta y los cruza contra listas de dominios maliciosos y reportes del CAI Virtual (mock) |
| Registro inmanipulable | `backend/app/services/certificado.py` — SHA-256 sobre texto + huellas de los adjuntos, verificable con `verificar_integridad()` |
| Canal accesible | `frontend/src/pages/Reportar.jsx` (drag & drop de PDF/TXT/PNG/JPEG, ≤2 MB, 3 archivos) + `backend/app/api/whatsapp.py` (webhook Twilio con `MediaUrl0..2` descargadas con auth) |
| Inteligencia territorial | `Dashboard.jsx` + `MapaCalor.jsx` — mapa de calor react-leaflet **restringido a Bosa**: `maxBounds`, centro `[4.619, -74.183]` y polígono de frontera; el backend garantiza coordenadas dentro del polígono (`app/data/bosa_polygon.py`) |

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
- `POST /api/whatsapp/webhook` — recibe mensajes de Twilio (`Body`, `MediaUrl0..2`), responde con TwiML XML
- `POST /api/reporte-web` — `{ mensaje, adjuntos?[{nombre, mime, base64}], barrio?, lat?, lng? }` → veredicto IA multimodal + cruce de fuentes + certificado SHA-256 (incluye huella de los archivos). Errores: `413` peso, `415` formato, `400` Base64 corrupto
