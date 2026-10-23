# Números reportados y vishing

## Qué se implementó

- **Consultar un número** (`/numero`): la persona escribe el número que la llamó
  (admite `+57`, espacios, guiones) y recibe un **nivel de riesgo explicable**,
  los **reportes de la comunidad**, las **coincidencias con fuentes oficiales**
  y una recomendación.
- **Reportar una llamada** (`/reportar?contexto=llamada`): el formulario permite
  contar qué le dijeron y adjuntar el número entrante. El análisis se marca como
  `vishing` y el número se cruza con el registro y con los reportes de vecinos.
- **API**: `GET /api/numeros/consultar?numero=...`, `GET /api/numeros/{numero}` y
  `GET /api/numeros/fuentes`.

## De dónde salen los datos

El registro vive en `backend/app/data/numeros.json` y tiene dos listas:

| Lista | Uso | Ejemplos |
|---|---|---|
| `numeros_confiables` | Líneas oficiales publicadas por la entidad. No se marcan como fraude. | 123 (Policía), 122 (Fiscalía), 165 (GAULA), 141 (ICBF), 195 (Bogotá), 601 592 0400 y 018000 910165 (SIC) |
| `numeros_reportados` | Números con reportes de autoridades, entidades o de la comunidad. Cada uno conserva `fuente`, `url`, `fecha` y `descripcion`. | Se llena con importaciones y con los reportes de la app |

**Importante:** a la fecha de este proyecto **no existe un listado público y
descargable de números de estafa publicado por el Gobierno colombiano o por la
Alcaldía de Bogotá**. Por eso el registro no inventa datos: parte de las líneas
oficiales verificables, se alimenta de los reportes comunitarios de la propia
cadena y acepta importar cualquier CSV/JSON oficial que se publique. Cada
coincidencia muestra su fuente y su enlace para que cualquiera la verifique.

## Importar un dataset oficial o comunitario

```bash
cd backend

# Números reportados (CSV con encabezados)
python scripts/importar_numeros.py --archivo datos_oficiales.csv \
  --fuente policia --nombre-fuente "Policía Nacional" \
  --url https://www.policia.gov.co/ --oficial --categoria vishing

# Líneas oficiales (no se marcan como fraude)
python scripts/importar_numeros.py --archivo lineas_oficiales.csv \
  --tipo confiable --fuente sic --nombre-fuente "SIC" \
  --url https://www.sic.gov.co/ --oficial

# Ver el estado del registro
python scripts/importar_numeros.py --listar

# Quitar un número
python scripts/importar_numeros.py --quitar 3001234567
```

Encabezados aceptados en CSV: `numero`, `categoria`, `fuente`, `url`, `fecha`,
`descripcion`, `entidad`, `demo` (también `phone`, `category`, `source`, `date`).
Categorías: `vishing`, `extorsion`, `sim_swapping`, `phishing`, `telemercadeo`,
`otro`. La escritura es atómica y deduplica por número + fuente.

Para la presentación se incluye `docs/ejemplos/numeros_demo.csv`, con números
**ficticios** marcados `demo: true`; la interfaz los muestra como
"demostración". Cárgalo así:

```bash
cd backend
python scripts/importar_numeros.py --archivo ../docs/ejemplos/numeros_demo.csv \
  --fuente demo --categoria vishing --demo
```

## Cómo se calcula el riesgo

Se combinan tres fuentes y se explica cada una:

1. **Registro**: el peso de la categoría (`vishing`/`extorsión` 60, SIM swapping
   55, phishing 50, telemercadeo 20) + 10 si la fuente es oficial + 8 por cada
   fuente adicional (máximo 20).
2. **Comunidad**: un solo reporte ya lleva el riesgo a **medio** (40); cada
   reporte adicional suma 6 hasta un máximo de 85. Con 6 reportes llega a **alto**.
3. **Señales del número**: oculto (55), inválido (45), internacional (25), móvil
   o fijo colombiano válido (10).

Umbrales: **bajo < 40**, **medio 40–69**, **alto ≥ 70** (los mismos de
`app/core/riesgo.py`). La confianza sube con coincidencias en el registro y con
reportes de vecinos.

En el flujo de reporte, el riesgo del número se aplica **una sola vez** en
`services/puntuacion.py`; la coincidencia del registro se muestra como hallazgo
con `gravedad: 0` para no contarla dos veces. El tipo `vishing` prima cuando la
persona reporta una llamada y el relato no define otra modalidad. El número
entrante también se agrega al historial comunitario, aunque no esté escrito en el
relato, para que la siguiente consulta lo vea.

## Límites y privacidad

- **No se interceptan llamadas.** Una web o una app iOS no pueden leer el audio
  de una llamada; en Android está restringido. El flujo es **reportar + consultar
  el número**, no escuchar la llamada en vivo.
- **Spoofing**: un estafador puede falsificar el número que aparece en pantalla.
  Por eso la interfaz nunca dice que un número sea "seguro": una línea oficial
  registrada solo evita el falso positivo, y siempre se advierte que la entidad
  no pide claves ni códigos.
- **Un número sin reportes no es garantía**: puede ser nuevo o haber cambiado de
  dueño. La recomendación se basa también en lo que la persona cuenta.
- **Datos personales (Ley 1581 de 2012)**: el número entrante se guarda completo
  solo en la colección privada `alertas_bosa`; en el panel público se enmascara.
  El audio de la llamada no se almacena: de los adjuntos solo queda el SHA-256 en
  la cadena. Los reportes comunitarios se guardan como conteos por número.
- **Abuso**: la consulta está limitada por IP; no se registra el número consultado
  en logs.
