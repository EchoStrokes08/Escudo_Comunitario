/**
 * Paleta oficial del proyecto:
 *  - Fondo oscuro, acentos en cyan #0e7490
 *  - Alertas en rojo #c3381f (alto) y amarillo #9a6b00 (medio)
 * TONOS son variantes luminosas de la misma paleta para texto y trazos sobre fondo oscuro.
 */
export const COLORES = {
    alto: '#c3381f',
    medio: '#9a6b00',
    bajo: '#0e7490',
}

export const TONOS = {
    alto: '#ff7a5c',
    medio: '#f2b544',
    bajo: '#38c6e8',
}

export function nivelRiesgo(nivel = 0) {
    if (nivel >= 70) return { color: COLORES.alto, tono: TONOS.alto, etiqueta: 'Alto', clase: 'riesgo-alto', id: 'alto' }
    if (nivel >= 40) return { color: COLORES.medio, tono: TONOS.medio, etiqueta: 'Medio', clase: 'riesgo-medio', id: 'medio' }
    return { color: COLORES.bajo, tono: TONOS.bajo, etiqueta: 'Bajo', clase: 'riesgo-bajo', id: 'bajo' }
}
