# 🛡️ Escudo Comunitario — Bosa

Ecosistema de prevención de fraude digital para la Localidad de Bosa (Hackathon Colombia 5.0).

## Capacidades

| Requisito | Implementación |
|---|---|
| **Detección y orientación con IA** | `services/analizador.py` — agente multimodal (Gemini con respaldo automático de modelos y claves, OpenAI opcional): texto, capturas (OCR), PDF y **notas de voz**. Devuelve riesgo, tipo de fraude, entidad suplantada, texto leído e indicadores. Defensa contra *prompt injection*. `services/puntuacion.py` calcula un **nivel de confianza explicable** (certeza del modelo + acuerdo con el análisis local + confirmaciones externas) y `services/orientacion.py` da un **plan de acción por tipo** (phishing, SIM swapping, estafa por WhatsApp, extorsión…) |
| **Verificación en tiempo real** | `services/verificador.py` — en paralelo y con timeouts: **RDAP** (antigüedad real del dominio), **suplantación de marca** y typosquatting, expansión de **enlaces acortados**, **OpenPhish** (sitios de phishing activos, sin clave), **URLhaus** (malware) y **Google Safe Browsing** (con clave), enlaces a **direcciones IP**, **historial comunitario** ("esta cuenta ya fue reportada N veces") y lista de referencia (marcada como demo). Verifica también lo leído en capturas y audios |
| **Registro trazable inmutable** | `services/registro.py` — cada reporte es un **bloque encadenado** (SHA-256 del JSON canónico + hash del anterior, en transacción) y se **sella en Bitcoin vía OpenTimestamps**. Página pública `/verificar` (íntegro/alterado, eslabones, comparación de huella en el navegador, descarga `.json` + `.ots`), **auditoría de toda la cadena** y **certificado imprimible con QR** (`/certificado/:hash`) |
| **Seguimiento del caso** | `services/seguimiento.py` — cada cambio de estado (**en revisión → remitido a Policía/Fiscalía → en investigación → cerrado**) es **otro bloque de la misma cadena** que apunta al certificado del reporte, con la huella de la nota pública, y se sella en Bitcoin: nadie puede reescribir cuándo se actuó ni qué se le respondió a la víctima. La víctima ve la **línea de tiempo** en `/verificar` y en el certificado, escribe `estado` en el bot y, si escribe `avísame`, **recibe cada avance por WhatsApp o Telegram** (único caso en que se guarda su contacto, con consentimiento, y se borra al cerrar el caso) |
| **Canal accesible** | **Respuestas en audio** (`services/voz.py`): quien manda una nota de voz recibe el veredicto **hablado** (MP3) en Telegram y WhatsApp; `escuchar` lo repite. **Cartel imprimible con QR** (`/cartel`) para tiendas y conjuntos. Web: texto, capturas, PDF, **grabación de voz** y **"Escuchar resultado"** (síntesis de voz). **Un mismo bot conversacional** en 4 canales: chat web (`/chat`), **Telegram** (`api/telegram.py`, gratis), **WhatsApp oficial de Meta** (`api/whatsapp_meta.py`, gratis con número de prueba) y WhatsApp vía Twilio. Notas de voz, capturas, UPZ con botones o ubicación 📍, `verificar <código>`, `estado`, `escuchar`, `avísame` y suscripción de líderes a alertas (`/alertas`) |
| **Panel territorial anonimizado** | `panel_publico` (solo lectura) sin datos personales: mensaje anonimizado, números enmascarados, enlaces desactivados, ubicación generalizada a ~200 m, reportante seudonimizado. Panel con mapa, **tendencia 14 días**, **tipos de fraude**, **entidades suplantadas**, **indicadores más reportados** y **alertas tempranas por UPZ** (aviso a líderes por WhatsApp). **Vista de autoridades** (`/autoridades`, token): casos por estado, **cambio de estado encadenado**, **casos agrupados por indicador** (una cuenta o dominio con N víctimas) con **paquete de evidencia** descargable, y exportación CSV |
| **Evaluación medible** | `scripts/evaluar.py` + `tests/datos/evaluacion.jsonl` (**160 mensajes etiquetados**: 70 fraudes de 9 modalidades y 90 legítimos difíciles, como alertas reales de bancos, códigos OTP o familiares pidiendo plata de verdad): exactitud, precisión, sensibilidad, F1, **falsos positivos**, acierto del tipo y **calibración de la confianza**. Botón **"¿Te sirvió? / Era legítimo"** en el veredicto para medir en uso real |

Diagnóstico en vivo: `GET /api/estado?probar_ia=1` · Documentación de la API: `/api/docs` · Pruebas: `cd backend && python -m pytest -q`

## Evaluación del detector

```bash
cd backend
python scripts/evaluar.py --pausa 1.5 --salida ../docs/evaluacion.md   # agente de IA (requiere GEMINI_API_KEY o GROQ_API_KEY en .env)
python scripts/evaluar.py --motor heuristico                          # solo el análisis local de respaldo
```

Por defecto no consulta la red (resultados reproducibles) y **desactiva la lista de referencia de demostración**, para que ningún mensaje acierte por estar en ella. Resultado del análisis local de respaldo (sin IA), en [`docs/evaluacion-heuristico.md`](docs/evaluacion-heuristico.md): **precisión 90.9 %, falsos positivos 2.2 %, sensibilidad 28.6 %**. Casi nunca alarma de más, pero deja pasar muchos fraudes: por eso es solo el respaldo del agente de IA. El informe marca con una advertencia si la IA no respondió.

## Despliegue de la versión 2 (orden importante)

1. **Variables de entorno en Vercel** (ver `backend/.env.example`): `GEMINI_API_KEY`, `GEMINI_MODEL=gemini-flash-latest`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `SAL_SEUDONIMO`, `AUTORIDADES_TOKEN`, `APP_URL` y opcionales (`URLHAUS_AUTH_KEY`, `GOOGLE_SAFE_BROWSING_KEY`, `LIDERES_WHATSAPP`).
2. **Push** y esperar el despliegue.
3. **Migrar los reportes existentes** a la cadena: `cd backend && python scripts/migrar_v2.py --aplicar`
4. **Publicar las reglas** (cierra la colección privada): `python scripts/desplegar_reglas.py`
5. Comprobar: `https://<app>/api/estado?probar_ia=1` debe mostrar `"motor": "llm"`.

Ensayo local sin tocar Firestore: `python scripts/servidor_demo.py` (base en memoria) + `npm run dev`.

## Arquitectura

### Vista general

```
   Canales de entrada                     Backend (FastAPI · Vercel)                       Datos y pruebas
 ┌───────────────────────┐        ┌──────────────────────────────────────┐        ┌───────────────────────────┐
 │ Formulario web        │──┐     │ services/procesamiento.py            │        │ Firestore                 │
 │ Chat web (/chat)      │──┤     │  1. Agente IA multimodal  ─┐ en      │        │  alertas_bosa   (privada) │
 │ Telegram              │──┼────▶│  2. Verificación abierta  ─┘ paralelo│───────▶│  panel_publico  (pública) │
 │ WhatsApp (Meta)       │──┤     │  3. Re-verificación de lo leído      │        │  registros      (pública) │
 │ WhatsApp (Twilio)     │──┘     │  4. Riesgo + confianza + plan        │        │  …                        │
 └───────────────────────┘        │  5. Bloque encadenado (certificado)  │        └───────────────────────────┘
                                  │  6. Sello en Bitcoin (OpenTimestamps)│───────▶ Calendarios OpenTimestamps
                                  └──────────────────────────────────────┘
                                                    │
                                                    ▼
             Frontend (React + Vite): panel en tiempo real · verificación pública · certificado con QR · autoridades
```

Vercel publica los dos servicios en el mismo dominio (`vercel.json`): `/api/*` va al backend y todo lo demás a la SPA de React.

### Backend — `backend/`

```
backend/
├── app/
│   ├── main.py                       App FastAPI, CORS (CORS_ORIGINS), registro de rutas, docs en /api/docs
│   ├── api/                          ── Rutas HTTP ──
│   │   ├── web_report.py             POST /api/reporte-web: formulario web (texto, adjuntos y voz en Base64)
│   │   ├── whatsapp.py               Webhook de Twilio (firma validada) + /api/whatsapp/simulador (chat web)
│   │   ├── whatsapp_meta.py          Webhook de WhatsApp Cloud API de Meta (verificación y mensajes)
│   │   ├── telegram.py               Webhook del bot de Telegram (/start, /verificar, /alertas, /cancelar)
│   │   ├── verificacion.py           Verificación pública (con línea de tiempo del caso), .json/.ots, auditoría, voz
│   │   ├── autoridades.py            Casos, cambio de estado, agrupados por indicador, evidencia, resumen (token)
│   │   └── estado.py                 Salud de cada componente; ?probar_ia=1 prueba el LLM en vivo
│   ├── core/                         ── Configuración y reglas comunes ──
│   │   ├── config.py                 Lectura de variables de entorno (.env / Vercel)
│   │   ├── riesgo.py                 Umbrales únicos de riesgo y confianza (iguales en el frontend)
│   │   ├── limite.py                 Límite de solicitudes por IP (12/min) contra inundación
│   │   └── red.py                    Contexto TLS compartido (cargar certificados cuesta ~0,5 s por cliente)
│   ├── services/                     ── Lógica de negocio ──
│   │   ├── procesamiento.py          Flujo único de un reporte, compartido por todos los canales
│   │   ├── analizador.py             Agente IA: Groq → Gemini → OpenAI → heurístico; texto, OCR, PDF, voz
│   │   ├── verificador.py            Fuentes abiertas: RDAP, OpenPhish, URLhaus, Safe Browsing, marcas…
│   │   ├── puntuacion.py             Riesgo final y nivel de confianza explicables (factores legibles)
│   │   ├── orientacion.py            Tipos de fraude y plan de acción por tipo (123, 122, CAI Virtual…)
│   │   ├── registro.py               Cadena de hashes SHA-256 (reportes y seguimiento) + OpenTimestamps + .ots
│   │   ├── seguimiento.py            Línea de tiempo del caso y avisos a la víctima que pidió "avísame"
│   │   ├── voz.py                    Veredicto hablado (MP3) para Telegram, WhatsApp y la web
│   │   ├── firebase_db.py            Persistencia en Firestore (transacciones de la cadena)
│   │   ├── anonimizar.py             Seudónimos y enmascarado de datos personales (Ley 1581 de 2012)
│   │   ├── archivos.py               Validación y normalización de adjuntos (imagen, PDF, TXT, audio)
│   │   ├── mensajeria.py             Envío/descarga de medios en Telegram y WhatsApp de Meta
│   │   ├── geolocalizacion.py        Ubicación por UPZ; todo punto cae dentro del polígono de Bosa
│   │   └── alertas_comunitarias.py   Detección de brotes por UPZ y aviso a líderes suscritos
│   └── data/
│       └── bosa_polygon.py           Polígono oficial de la Localidad 07 (fuente única de verdad)
├── scripts/
│   ├── servidor_demo.py              Backend local con base EN MEMORIA (ensayo de la demo)
│   ├── evaluar.py                    Métricas del detector con el conjunto etiquetado
│   ├── migrar_v2.py                  Pasa los reportes antiguos a la cadena v2 (idempotente)
│   ├── desplegar_reglas.py           Publica firestore.rules sin Firebase CLI
│   ├── configurar_telegram.py        Registra webhook, comandos y descripción del bot
│   └── probar_firebase.py            Smoke test: escribe, lee y borra en Firestore
├── tests/
│   ├── test_nucleo.py                Cadena, anonimización, verificación local, confianza, adjuntos
│   ├── test_flujo.py                 Flujo completo de la API con base en memoria y red simulada
│   ├── test_canales.py               Telegram y WhatsApp de Meta con la API de cada plataforma simulada
│   ├── test_seguimiento.py           Estados encadenados, avisos, agrupados, evidencia, opinión y voz
│   ├── test_evaluacion.py            Conjunto etiquetado bien formado y respaldo local sin falsas alarmas
│   └── datos/evaluacion.jsonl        160 mensajes etiquetados (fraudes y legítimos)
├── requirements.txt                  Producción (FastAPI, firebase-admin, httpx, twilio, pypdf…)
├── requirements-dev.txt              Desarrollo y pruebas (pytest, pytest-asyncio)
└── .env.example                      Plantilla de variables de entorno
```

### Frontend — `frontend/`

```
frontend/src/
├── main.jsx                  Arranque de React e inicio temprano de la suscripción a Firestore
├── App.jsx                   Navegación y rutas
├── styles.css                Estilos globales (tema oscuro, acentos cyan)
├── pages/
│   ├── Dashboard.jsx         /                     Panel: mapa, tendencia, tipos, entidades, alertas por UPZ
│   ├── Reportar.jsx          /reportar             Formulario: texto, capturas, PDF, voz y ubicación
│   ├── Chat.jsx              /chat                 Chat web con el mismo bot de WhatsApp y Telegram
│   ├── Verificar.jsx         /verificar[/:codigo]  Verificación pública, eslabones, huella en el navegador
│   ├── Certificado.jsx       /certificado/:codigo  Certificado de reporte imprimible con QR y estado del caso
│   ├── Cartel.jsx            /cartel               Cartel imprimible con QR de WhatsApp, Telegram y chat
│   └── Autoridades.jsx       /autoridades          Casos, cambio de estado, agrupados y evidencia (token)
├── components/
│   ├── Veredicto.jsx         Riesgo, confianza, factores, plan de acción, "Escuchar resultado" y "¿Te sirvió?"
│   ├── LineaTiempo.jsx       Línea de tiempo del caso (cada paso, un bloque verificable)
│   ├── GrabadorVoz.jsx       Grabación de notas de voz desde el navegador
│   ├── MapaCalor.jsx         Mapa de reportes por UPZ (react-leaflet)
│   ├── GraficaTendencia.jsx  Tendencia de reportes de los últimos 14 días
│   ├── CodigoQR.jsx          QR hacia la página pública de verificación
│   └── Icono.jsx             Iconos de la interfaz
├── services/
│   ├── api.js                Cliente del backend (mismo dominio en Vercel, proxy de Vite en local)
│   ├── firebase.js           Inicialización de Firebase (configuración web pública)
│   └── alertas.js            Suscripción única en tiempo real a panel_publico
├── data/
│   ├── bosaPolygon.js        Réplica del polígono de Bosa para Leaflet
│   ├── upz.js                Las 5 UPZ de Bosa (Apogeo, Bosa Occidental, Bosa Central, El Porvenir, Tintal Sur)
│   └── barrios.js            Compatibilidad: re-exporta upz.js
├── hooks/
│   └── animacion.js          Animaciones (respeta "reducir movimiento")
└── utils/
    ├── riesgo.js             Umbrales y colores de riesgo (iguales al backend)
    ├── canales.js            Enlaces públicos a Telegram (@EscudoBosaBot) y WhatsApp
    ├── estados.js            Estados del caso (iguales al backend)
    └── tiempo.js             Formato de fechas relativas
```

### Colecciones de Firestore

| Colección | Acceso | Contenido |
|---|---|---|
| `alertas_bosa/{hash}` | 🔒 Privada (solo backend) | Caso completo para autoridades; el teléfono se guarda solo como seudónimo |
| `panel_publico/{hash}` | 👁️ Pública, solo lectura | Versión anonimizada que alimenta el panel |
| `registros/{hash}` | 👁️ Pública, solo lectura | Bloques de la cadena: reportes y seguimiento del caso (estado, actor, nota anonimizada) |
| `alertas_comunitarias/{id}` | 👁️ Pública, solo lectura | Brotes detectados por UPZ |
| `cadena/estado` | 🔒 Privada | Altura y último hash (se actualiza en transacción) |
| `indicadores/{id}` | 🔒 Privada | Veces que se reportó cada dominio, cuenta o teléfono |
| `conversaciones/{seudonimo}` | 🔒 Privada | Estado de la conversación del bot |
| `suscriptores_alertas/{id}` | 🔒 Privada | Líderes que reciben alertas (Telegram / WhatsApp) |
| `avisos_caso/{id}` | 🔒 Privada | Contacto de quien pidió "avísame" para su caso (con consentimiento; se borra al cerrar) |
| `retroalimentacion/{id}` | 🔒 Privada | "¿Te sirvió?" / "Era legítimo" de cada veredicto |

### Tecnologías

| Capa | Herramientas |
|---|---|
| Backend | Python, FastAPI, httpx (asíncrono), pypdf, Twilio SDK, firebase-admin |
| IA | Groq (Qwen y Whisper para voz), Google Gemini, OpenAI (opcional), análisis heurístico local de respaldo |
| Fuentes abiertas | RDAP, OpenPhish, URLhaus (abuse.ch), Google Safe Browsing |
| Trazabilidad | SHA-256 encadenado, OpenTimestamps (sello en Bitcoin) |
| Frontend | React 18, Vite, React Router, Leaflet / react-leaflet, qrcode, Web Speech API |
| Datos y despliegue | Firebase Firestore, Vercel Services |

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

Documentación interactiva completa en `/api/docs`.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/api/estado` | Salud de cada componente (sin secretos); `?probar_ia=1` hace una llamada real al LLM |
| **Reporte** | | |
| `POST` | `/api/reporte-web` | `{ mensaje, adjuntos?[{nombre, mime, base64}], barrio?, lat?, lng? }` → veredicto IA + verificación + confianza + plan + certificado. Errores: `413` peso, `415` formato, `400` Base64 corrupto |
| **Canales conversacionales** | | |
| `POST` | `/api/whatsapp/simulador` | Chat web (`/chat`): misma conversación que el bot de WhatsApp |
| `POST` | `/api/whatsapp/webhook` | Twilio (form-encoded, firma `X-Twilio-Signature` validada) → responde TwiML |
| `GET` | `/api/whatsapp-meta/webhook` | Verificación del webhook de Meta (`hub.challenge`) |
| `POST` | `/api/whatsapp-meta/webhook` | Mensajes de WhatsApp Cloud API (texto, imagen, audio, documento, ubicación, lista de UPZ) |
| `POST` | `/api/telegram/webhook` | Mensajes del bot de Telegram (cabecera secreta validada) |
| **Verificación y cadena** | | |
| `GET` | `/api/verificar/{codigo}` | ¿El reporte existe y está íntegro? (hash completo o prefijo), con la línea de tiempo del caso |
| `GET` | `/api/voz/{codigo}.mp3` | Veredicto hablado de la versión pública del caso |
| `POST` | `/api/retroalimentacion/{hash}` | `{ util?, era_legitimo? }`: "¿te sirvió?" y falsos positivos |
| `GET` | `/api/verificar/{hash}/registro.json` | JSON canónico del bloque (su SHA-256 es el certificado) |
| `GET` | `/api/verificar/{hash}/prueba.ots` | Prueba OpenTimestamps, verificable en opentimestamps.org |
| `GET` | `/api/cadena/estado` | Altura y último hash de la cadena |
| `GET` | `/api/cadena/auditoria` | Recalcula todos los hashes y enlaces de la cadena |
| `POST` | `/api/cadena/sellar/{codigo}` | Sella un reporte en Bitcoin justo después del veredicto (público, idempotente, limitado por IP) |
| `POST` | `/api/cadena/anclar-pendientes` | Sella todos los reportes pendientes (token) |
| **Autoridades** | | |
| `GET` | `/api/autoridades/casos` | Casos completos (`Authorization: Bearer <AUTORIDADES_TOKEN>`); `?formato=csv` para exportar |
| `POST` | `/api/autoridades/casos/{hash}/estado` | `{ estado, actor, nota? }`: nuevo bloque de seguimiento, sellado y avisado a la víctima |
| `GET` | `/api/autoridades/agrupados` | Dominios, cuentas y teléfonos reportados por varias personas |
| `GET` | `/api/autoridades/indicador/{id}/evidencia` | Paquete de evidencia (JSON) con todos los casos del indicador |
| `GET` | `/api/autoridades/resumen` | Casos por estado y retroalimentación de las personas |
