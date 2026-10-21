import { useMemo, useState } from 'react'

const DIAS = 14
const NIVELES = [
    { id: 'alto', etiqueta: 'Alto' },
    { id: 'medio', etiqueta: 'Medio' },
    { id: 'bajo', etiqueta: 'Bajo' },
]

const claveDia = (fecha) => {
    const d = new Date(fecha)
    return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
}

/** Reportes por día (últimos 14 días), apilados por nivel de riesgo. */
export default function GraficaTendencia({ reportes, ahora }) {
    const [activo, setActivo] = useState(null)

    const dias = useMemo(() => {
        const hoy = new Date(ahora)
        hoy.setHours(0, 0, 0, 0)
        const lista = Array.from({ length: DIAS }, (_, i) => {
            const d = new Date(hoy)
            d.setDate(d.getDate() - (DIAS - 1 - i))
            return { fecha: d, clave: claveDia(d), alto: 0, medio: 0, bajo: 0, total: 0 }
        })
        const porClave = Object.fromEntries(lista.map(d => [d.clave, d]))
        for (const r of reportes) {
            const dia = r.fecha && porClave[claveDia(r.fecha)]
            if (!dia) continue
            dia[r.nivel] += 1
            dia.total += 1
        }
        return lista
    }, [reportes, ahora])

    const maximo = Math.max(1, ...dias.map(d => d.total))
    const totalPeriodo = dias.reduce((s, d) => s + d.total, 0)
    const ultimos7 = dias.slice(7).reduce((s, d) => s + d.total, 0)
    const previos7 = dias.slice(0, 7).reduce((s, d) => s + d.total, 0)
    const variacion = previos7 ? Math.round(((ultimos7 - previos7) / previos7) * 100) : null
    const formato = (f) => f.toLocaleDateString('es-CO', { weekday: 'short', day: 'numeric', month: 'short' })

    return (
        <div className="grafica-tendencia">
            <div className="grafica-resumen">
                <span><strong>{totalPeriodo}</strong> reportes en 14 días</span>
                {variacion !== null && (
                    <span className={variacion > 0 ? 'texto-alto' : 'texto-bajo'}>
                        {variacion > 0 ? '▲' : '▼'} {Math.abs(variacion)}% vs. semana anterior
                    </span>
                )}
            </div>
            <ul className="leyenda-grafica" aria-hidden="true">
                {NIVELES.map(n => <li key={n.id}><i className={`muestra-grafica grafica-${n.id}`} />{n.etiqueta}</li>)}
            </ul>
            <div className="grafica-area" role="img" aria-label={`Reportes por día en los últimos 14 días: ${totalPeriodo} en total`}>
                {dias.map((d, i) => (
                    <div
                        key={d.clave}
                        className={`grafica-columna ${activo === i ? 'activa' : ''}`}
                        tabIndex={0}
                        onMouseEnter={() => setActivo(i)}
                        onMouseLeave={() => setActivo(null)}
                        onFocus={() => setActivo(i)}
                        onBlur={() => setActivo(null)}
                        aria-label={`${formato(d.fecha)}: ${d.total} reportes, ${d.alto} alto, ${d.medio} medio, ${d.bajo} bajo`}
                    >
                        <div className="grafica-pila" style={{ height: `${(d.total / maximo) * 100}%` }}>
                            {NIVELES.filter(n => d[n.id] > 0).map(n => (
                                <span key={n.id} className={`grafica-${n.id}`} style={{ flexGrow: d[n.id] }} />
                            ))}
                        </div>
                        <span className="grafica-eje">{i % 2 === 1 || i === DIAS - 1 ? d.fecha.getDate() : ''}</span>
                        {activo === i && (
                            <div className={`grafica-tooltip ${i > DIAS - 4 ? 'izquierda' : ''}`} role="tooltip">
                                <strong>{formato(d.fecha)}</strong>
                                <span className="tooltip-total">{d.total} {d.total === 1 ? 'reporte' : 'reportes'}</span>
                                {NIVELES.map(n => (
                                    <span key={n.id} className="tooltip-fila"><i className={`muestra-grafica grafica-${n.id}`} />{n.etiqueta}<b>{d[n.id]}</b></span>
                                ))}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    )
}
