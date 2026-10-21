/** Canales de mensajería públicos del bot (configurables por variables de Vite). */
export const TELEGRAM_BOT = import.meta.env.VITE_TELEGRAM_BOT || 'EscudoBosaBot'
export const URL_TELEGRAM = `https://t.me/${TELEGRAM_BOT}`

// Número de WhatsApp de Meta (número de prueba: solo responde a los números registrados en Meta)
export const WHATSAPP_NUMERO = (import.meta.env.VITE_WHATSAPP_NUMERO || '15551967584').replace(/\D/g, '')
export const URL_WHATSAPP = `https://wa.me/${WHATSAPP_NUMERO}?text=${encodeURIComponent('Hola Escudo Comunitario')}`
export const WHATSAPP_VISIBLE = `+${WHATSAPP_NUMERO.slice(0, 1)} ${WHATSAPP_NUMERO.slice(1, 4)} ${WHATSAPP_NUMERO.slice(4, 7)} ${WHATSAPP_NUMERO.slice(7)}`
