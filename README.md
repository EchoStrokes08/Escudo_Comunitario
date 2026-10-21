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

### 1. Backend

```bash
cd backend
cp .env.example .env       # completa Twilio, CORS_ORIGINS y GEMINI_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Firebase (base de datos):**

- **Local**: la credencial ya está en `backend/serviceAccountKey.json` (fallback automático de `services/firebase_db.py`).
- **Vercel**: pega el JSON completo de la service account como variable `FIREBASE_CREDENTIALS` en *Project → Settings → Environment Variables* (es una sola línea; el `\n` de la clave privada viene escapado dentro del JSON).
- **Verificación**: desde `/backend` corre el smoke test — escribe, lee y borra un documento de prueba en `alertas_bosa`:
  ```bash
  python scripts/probar_firebase.py
  ```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env` ya contiene la web config pública de Firebase (`VITE_FIREBASE_*`) y `VITE_API_URL` para el backend.

### 3. Reglas de Firestore

`firestore.rules` abre **únicamente** `alertas_bosa` (lectura/escrita sin login, para que el Dashboard funcione) y cierra el resto de la base. Despliega con:

```bash
firebase deploy --only firestore:rules
```

o pega las reglas manualmente en la consola de Firebase → Firestore → Rules.

> ⚠️ Para un despliegue real, restringe `alertas_bosa` con `request.auth != null` (auth anónima de Firebase).

### 4. Seguridad de credenciales

- 🔒 Los secretos (`.env`, `serviceAccountKey.json`) están en `.gitignore` y **no se suben al repo**.
- 🔄 **Rotación de claves**: si una service account o web config se compartió fuera de un canal seguro (chat, pantalla), rota la clave en Google Cloud Console → IAM → Service Accounts → ADD KEY → *Create new key* y elimina la anterior. La web config (`VITE_FIREBASE_*`) es pública por diseño y no da acceso de escritura.

### 5. End-to-end (smoke test manual)

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload
# Terminal 2
cd frontend && npm run dev
# Terminal 3 (reporte de prueba)
curl -X POST http://localhost:8000/api/reporte-web \
  -H "Content-Type: application/json" \
  -d "{\"mensaje\": \"Felicidades, ganaste un premio. Consigna $50.000 en Nequi 3001234567 antes de las 6pm: www.premios-bogota.top\"}"
```

El documento debe aparecer en Firestore (`alertas_bosa`) y renderizarse en el Dashboard en tiempo real.

## Endpoints

- `GET /` — health check
- `POST /api/whatsapp/webhook` — recibe mensajes de Twilio (`Body`, `MediaUrl0..2`), responde con TwiML XML
- `POST /api/reporte-web` — `{ mensaje, adjuntos?[{nombre, mime, base64}], barrio?, lat?, lng? }` → veredicto IA multimodal + cruce de fuentes + certificado SHA-256 (incluye huella de los archivos). Errores: `413` peso, `415` formato, `400` Base64 corrupto
