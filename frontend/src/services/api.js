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
export const auditarCadena = () => pedir('/api/cadena/auditoria')
export const urlRegistroJson = (hash) => `${API_URL}/api/verificar/${hash}/registro.json`
export const urlPruebaOts = (hash) => `${API_URL}/api/verificar/${hash}/prueba.ots`

/** SHA-256 en el navegador: el texto nunca sale del dispositivo. */
export async function sha256Texto(texto) {
    const normalizado = (texto || '').replace(/\r\n/g, '\n').trim()
    const datos = new TextEncoder().encode(normalizado)
    const resumen = await crypto.subtle.digest('SHA-256', datos)
    return [...new Uint8Array(resumen)].map(b => b.toString(16).padStart(2, '0')).join('')
}
