const formato = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })

const UNIDADES = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
]

/** "hace 5 minutos", "ayer"… a partir de una fecha ISO. */
export function tiempoRelativo(fecha, ahora = Date.now()) {
    const marca = new Date(fecha).getTime()
    if (Number.isNaN(marca)) return ''
    const segundos = Math.round((marca - ahora) / 1000)
    for (const [unidad, tamano] of UNIDADES) {
        if (Math.abs(segundos) >= tamano) return formato.format(Math.round(segundos / tamano), unidad)
    }
    return 'justo ahora'
}
