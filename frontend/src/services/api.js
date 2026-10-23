/** Cliente mínimo del backend FastAPI (mismo dominio en Vercel, proxy de Vite en local). */
export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export async function pedir(ruta, opciones = {}) {
    let respuesta
    try {
        respuesta = await fetch(`${API_URL}${ruta}`, opciones)
    } catch {
        throw new Error('No pudimos conectar con el servidor. Verifica tu conexión e inténtalo de nuevo.')
    }
    if (!respuesta.ok) {
        const detalle = await respuesta.json().catch(() => null)
        const error = new Error(detalle?.detail || `El servicio respondió con error (${respuesta.status}).`)
        error.status = respuesta.status
        throw error
    }
    const tipo = respuesta.headers.get('content-type') || ''
    return tipo.includes('application/json') ? respuesta.json() : respuesta.blob()
}

export const verificarCertificado = (codigo) => pedir(`/api/verificar/${encodeURIComponent(codigo)}`)
export const consultarNumero = (numero) => pedir(`/api/numeros/consultar?numero=${encodeURIComponent(numero)}`)
export const fuentesNumeros = () => pedir('/api/numeros/fuentes')
export const auditarCadena = () => pedir('/api/cadena/auditoria')
/** Sella el bloque en Bitcoin (OpenTimestamps) sin hacer esperar el veredicto. */
export const sellarCertificado = (hash) => pedir(`/api/cadena/sellar/${hash}`, { method: 'POST' })
export const urlRegistroJson = (hash) => `${API_URL}/api/verificar/${hash}/registro.json`
export const urlPruebaOts = (hash) => `${API_URL}/api/verificar/${hash}/prueba.ots`

/** SHA-256 en el navegador: el texto nunca sale del dispositivo. */
export async function sha256Texto(texto) {
    const normalizado = (texto || '').replace(/\r\n/g, '\n').trim()
    const datos = new TextEncoder().encode(normalizado)
    const resumen = await crypto.subtle.digest('SHA-256', datos)
    return [...new Uint8Array(resumen)].map(b => b.toString(16).padStart(2, '0')).join('')
}

/** Veredicto hablado (MP3) de la versión pública del caso. */
export const urlVoz = (hash) => `${API_URL}/api/voz/${hash}.mp3`
/** "¿Te sirvió?" / "Era legítimo" de quien recibió el veredicto. */
export const enviarOpinion = (hash, opinion) => pedir(`/api/retroalimentacion/${hash}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(opinion),
})

// --- Autoridades (token Bearer) ---
const conToken = (token, opciones = {}) => ({ ...opciones, headers: { ...(opciones.headers || {}), Authorization: `Bearer ${token}` } })
export const casosAutoridades = (token) => pedir('/api/autoridades/casos', conToken(token))
export const resumenAutoridades = (token) => pedir('/api/autoridades/resumen', conToken(token))
export const casosAgrupados = (token) => pedir('/api/autoridades/agrupados', conToken(token))
export const paqueteEvidencia = (token, id) => pedir(`/api/autoridades/indicador/${encodeURIComponent(id)}/evidencia`, conToken(token))
export const exportarCasosCsv = (token) => pedir('/api/autoridades/casos?formato=csv', conToken(token))
export const cambiarEstadoCaso = (token, hash, cambio) => pedir(`/api/autoridades/casos/${hash}/estado`, conToken(token, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cambio),
}))

/** Descarga un Blob (o JSON) como archivo. */
export function descargarArchivo(contenido, nombre) {
    const blob = contenido instanceof Blob ? contenido : new Blob([JSON.stringify(contenido, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = Object.assign(document.createElement('a'), { href: url, download: nombre })
    a.click()
    URL.revokeObjectURL(url)
}
