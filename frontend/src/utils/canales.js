/** Canales de mensajería públicos del bot (configurables por variables de Vite). */
export const TELEGRAM_BOT = import.meta.env.VITE_TELEGRAM_BOT || 'EscudoBosaBot'
export const URL_TELEGRAM = `https://t.me/${TELEGRAM_BOT}`
