/**
 * Paleta oficial del proyecto:
 *  - Fondo oscuro, acentos en cyan #0e7490
 *  - Alertas en rojo #c3381f (alto) y amarillo #9a6b00 (medio)
 */
export const COLORES = {
    alto: '#c3381f',
    medio: '#9a6b00',
    bajo: '#0e7490',
}

export function nivelRiesgo(nivel = 0) {
    if (nivel >= 70) return { color: COLORES.alto, etiqueta: 'Alto', clase: 'riesgo-alto' }
    if (nivel >= 40) return { color: COLORES.medio, etiqueta: 'Medio', clase: 'riesgo-medio' }
    return { color: COLORES.bajo, etiqueta: 'Bajo', clase: 'riesgo-bajo' }
}
