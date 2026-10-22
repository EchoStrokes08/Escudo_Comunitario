/**
 * Paleta oficial del proyecto:
 *  - Fondo oscuro, acentos en cyan #0e7490
 *  - Alertas en rojo #c3381f (alto) y amarillo #9a6b00 (medio)
 * TONOS son variantes luminosas de la misma paleta para texto y trazos sobre fondo oscuro.
 *
 * Umbrales idénticos a backend/app/core/riesgo.py (alto ≥ 70, medio ≥ 40).
 */
export const UMBRAL_ALTO = 70
export const UMBRAL_MEDIO = 40

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
    if (nivel >= UMBRAL_ALTO) return { color: COLORES.alto, tono: TONOS.alto, etiqueta: 'Alto', clase: 'riesgo-alto', id: 'alto' }
    if (nivel >= UMBRAL_MEDIO) return { color: COLORES.medio, tono: TONOS.medio, etiqueta: 'Medio', clase: 'riesgo-medio', id: 'medio' }
    return { color: COLORES.bajo, tono: TONOS.bajo, etiqueta: 'Bajo', clase: 'riesgo-bajo', id: 'bajo' }
}

export function nivelConfianza(confianza = 0) {
    if (confianza >= 75) return { id: 'alta', etiqueta: 'Alta' }
    if (confianza >= 50) return { id: 'media', etiqueta: 'Media' }
    return { id: 'baja', etiqueta: 'Baja' }
}

/** Mismos tipos que backend/app/services/orientacion.py */
export const TIPOS_FRAUDE = {
    phishing: 'Phishing',
    malware: 'Malware',
    sim_swapping: 'SIM swapping',
    estafa_whatsapp: 'Estafa por WhatsApp',
    suplantacion_entidad: 'Suplantación de entidad',
    premio_falso: 'Premio o subsidio falso',
    compra_falsa: 'Venta o compra falsa',
    extorsion: 'Extorsión',
    empleo_falso: 'Empleo o inversión falsa',
    otro: 'Otro fraude',
    legitimo: 'Sin indicios',
}

export const nombreTipo = (id) => TIPOS_FRAUDE[id] || TIPOS_FRAUDE.otro
