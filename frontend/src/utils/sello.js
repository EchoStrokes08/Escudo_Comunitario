/**
 * Sello de tiempo en Bitcoin (OpenTimestamps), igual a los estados de backend/app/services/registro.py:
 *   en_proceso → pendiente_bitcoin (en calendarios, esperando el bloque) → confirmado_bitcoin
 */
export const URL_BLOQUE_BITCOIN = (altura) => `https://mempool.space/block/${altura}`

/** ¿Vale la pena pedir al backend que selle o complete la prueba? */
export const selloIncompleto = (anclaje) =>
    !anclaje?.descargable || anclaje?.estado === 'pendiente_bitcoin'

const calendarios = (anclaje) => {
    const n = anclaje?.calendarios?.length || (anclaje?.calendario ? 1 : 0)
    return n === 1 ? '1 calendario' : `${n} calendarios`
}

/** Frase corta del estado del sello para el veredicto y el certificado. */
export function textoSello(anclaje) {
    const estado = anclaje?.estado
    if (estado === 'confirmado_bitcoin' && anclaje.bitcoin) {
        const fecha = new Date(anclaje.bitcoin.hora_bloque).toLocaleString('es-CO')
        return `Confirmado en el bloque ${anclaje.bitcoin.altura.toLocaleString('es-CO')} de Bitcoin (${fecha})`
    }
    if (estado === 'pendiente_bitcoin') {
        return `Sellado en ${calendarios(anclaje)} de OpenTimestamps · confirmación en Bitcoin en unas horas`
    }
    if (estado === 'invalido') return 'La prueba de OpenTimestamps no coincide con Bitcoin'
    if (estado === 'en_proceso') return 'Sellando en Bitcoin vía OpenTimestamps…'
    return 'Sello en Bitcoin pendiente: se reintentará'
}
