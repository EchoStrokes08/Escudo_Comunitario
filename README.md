# 🛡️ Escudo Comunitario — Bosa

Ecosistema de prevención de fraude digital para la Localidad de Bosa (Hackathon Colombia 5.0).

## Capacidades

| Requisito | Implementación |
|---|---|
| **Detección y orientación con IA** | `services/analizador.py` — agente multimodal (Gemini con respaldo automático de modelos y claves, OpenAI opcional): texto, capturas (OCR), PDF y **notas de voz**. Devuelve riesgo, tipo de fraude, entidad suplantada, texto leído e indicadores. Defensa contra *prompt injection*. `services/puntuacion.py` calcula un **nivel de confianza explicable** (certeza del modelo + acuerdo con el análisis local + confirmaciones externas) y `services/orientacion.py` da un **plan de acción por tipo** (phishing, SIM swapping, estafa por WhatsApp, extorsión…) |
| **Verificación en tiempo real** | `services/verificador.py` — en paralelo y con timeouts: **RDAP** (antigüedad real del dominio), **suplantación de marca** y typosquatting, expansión de **enlaces acortados**, **OpenPhish** (sitios de phishing activos, sin clave), **URLhaus** (malware) y **Google Safe Browsing** (con clave), enlaces a **direcciones IP**, **historial comunitario** ("esta cuenta ya fue reportada N veces") y lista de referencia (marcada como demo). Verifica también lo leído en capturas y audios |
| **Registro trazable inmutable** | `services/registro.py` — cada reporte es un **bloque encadenado** (SHA-256 del JSON canónico + hash del anterior, en transacción) y se **sella en Bitcoin vía OpenTimestamps**. Página pública `/verificar` (íntegro/alterado, eslabones, comparación de huella en el navegador, descarga `.json` + `.ots`), **auditoría de toda la cadena** y **certificado imprimible con QR** (`/certificado/:hash`) |
| **Canal accesible** | Web: texto, capturas, PDF, **grabación de voz** y **"Escuchar resultado"** (síntesis de voz). **Un mismo bot conversacional** en 4 canales: chat web (`/chat`), **Telegram** (`api/telegram.py`, gratis), **WhatsApp oficial de Meta** (`api/whatsapp_meta.py`, gratis con número de prueba) y WhatsApp vía Twilio. Notas de voz, capturas, UPZ con botones o ubicación 📍, `verificar <código>` y suscripción de líderes a alertas (`/alertas`) |
| **Panel territorial anonimizado** | `panel_publico` (solo lectura) sin datos personales: mensaje anonimizado, números enmascarados, enlaces desactivados, ubicación generalizada a ~200 m, reportante seudonimizado. Panel con mapa, **tendencia 14 días**, **tipos de fraude**, **entidades suplantadas**, **indicadores más reportados** y **alertas tempranas por UPZ** (aviso a líderes por WhatsApp). **Vista de autoridades** (`/autoridades`, token) con exportación CSV |

Diagnóstico en vivo: `GET /api/estado?probar_ia=1` · Documentación de la API: `/api/docs` · Pruebas: `cd backend && python -m pytest -q`

## Despliegue de la versión 2 (orden importante)

1. **Variables de entorno en Vercel** (ver `backend/.env.example`): `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-flash-latest`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `SAL_SEUDONIMO`, `AUTORIDADES_TOKEN`, `APP_URL` y opcionales (`URLHAUS_AUTH_KEY`, `GOOGLE_SAFE_BROWSING_KEY`, `LIDERES_WHATSAPP`).
2. **Push** y esperar el despliegue.
3. **Migrar los reportes existentes** a la cadena: `cd backend && python scripts/migrar_v2.py --aplicar`
4. **Publicar las reglas** (cierra la colección privada): `python scripts/desplegar_reglas.py`
5. Comprobar: `https://<app>/api/estado?probar_ia=1` debe mostrar `"motor": "llm"`.

Ensayo local sin tocar Firestore: `python scripts/servidor_demo.py` (base en memoria) + `npm run dev`.

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

`firestore.rules` permite **solo lectura** de `panel_publico`, `registros` y `alertas_comunitarias` (sin datos personales) y **nadie escribe desde el navegador**: todo entra por el backend (Admin SDK). `alertas_bosa` (casos completos) queda privada. Publica las reglas sin Firebase CLI con:

```bash
cd backend && python scripts/desplegar_reglas.py
```

o pega las reglas manualmente en la consola de Firebase → Firestore → Rules.

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

El caso completo queda en `alertas_bosa` (privada), su versión anonimizada en `panel_publico` (aparece en el Dashboard en tiempo real) y su bloque en `registros`.

## Endpoints

- `GET /` — health check
- `POST /api/whatsapp/webhook` — recibe mensajes de Twilio (`Body`, `MediaUrl0..2`), responde con TwiML XML
- `POST /api/reporte-web` — `{ mensaje, adjuntos?[{nombre, mime, base64}], barrio?, lat?, lng? }` → veredicto IA multimodal + cruce de fuentes + certificado SHA-256 (incluye huella de los archivos). Errores: `413` peso, `415` formato, `400` Base64 corrupto
