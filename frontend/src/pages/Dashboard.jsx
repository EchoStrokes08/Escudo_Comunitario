import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import MapaCalor, { tieneCoordenadas } from '../components/MapaCalor.jsx'
import { useAlertas } from '../services/alertas.js'
import Icono from '../components/Icono.jsx'
import { nivelRiesgo } from '../utils/riesgo.js'
import { tiempoRelativo } from '../utils/tiempo.js'
import { useAhora, useContador } from '../hooks/animacion.js'
import { UPZ_BOSA } from '../data/upz.js'

const FILTROS = [
    { id: 'todos', etiqueta: 'Todos' },
    { id: 'alto', etiqueta: 'Alto' },
    { id: 'medio', etiqueta: 'Medio' },
    { id: 'bajo', etiqueta: 'Bajo' },
]

const POR_PAGINA = 12

function TarjetaEstadistica({ valor, sufijo = '', etiqueta, detalle, icono, variante }) {
    const animado = useContador(valor)
    return (
        <div className={`tarjeta-estadistica ${variante ? `estadistica-${variante}` : ''}`}>
            <span className="estadistica-icono"><Icono nombre={icono} tamano={18} /></span>
            <span className="valor">{animado}{sufijo}</span>
            <span className="etiqueta">{etiqueta}</span>
            {detalle && <span className="detalle">{detalle}</span>}
        </div>
    )
}

export default function Dashboard() {
    const { alertas, cargando, error, desdeCache, actualizado, nuevos } = useAlertas()
    const errorConexion = Boolean(error)
    const [filtro, setFiltro] = useState('todos')
    const [busqueda, setBusqueda] = useState('')
    const [visibles, setVisibles] = useState(POR_PAGINA)
    const [seleccionado, setSeleccionado] = useState(null)

    const seccionMapa = useRef(null)
    const ahora = useAhora()

    // Una sola pasada sobre los reportes (ya normalizados con lat/lng y nivel precalculados)
    const estadisticas = useMemo(() => {
        const conteo = { alto: 0, medio: 0, bajo: 0 }
        let suma = 0
        let ultimas24h = 0
        for (const a of alertas) {
            conteo[a.nivel] += 1
            suma += a.nivel_riesgo
            if (a.fecha && ahora - new Date(a.fecha).getTime() < 86_400_000) ultimas24h += 1
        }
        const total = alertas.length
        return { total, ...conteo, promedio: total ? Math.round(suma / total) : 0, ultimas24h }
    }, [alertas, ahora])

    const rankingUpz = useMemo(() => {
        const conteo = Object.fromEntries(UPZ_BOSA.map(u => [u.nombre.toLowerCase(), { total: 0, alto: 0 }]))
        for (const a of alertas) {
            const fila = conteo[(a.upz || '').toLowerCase()]
            if (!fila) continue
            fila.total += 1
            if (a.nivel === 'alto') fila.alto += 1
        }
        const filas = UPZ_BOSA.map(u => ({ ...u, ...conteo[u.nombre.toLowerCase()] })).sort((a, b) => b.total - a.total)
        const maximo = Math.max(1, ...filas.map(f => f.total))
        return filas.map(f => ({ ...f, proporcion: f.total / maximo }))
    }, [alertas])

    const filtradas = useMemo(() => {
        const texto = busqueda.trim().toLowerCase()
        return alertas.filter(a => {
            if (filtro !== 'todos' && a.nivel !== filtro) return false
            if (!texto) return true
            return [a.mensaje_original, a.upz, a.barrio, a.certificado, ...(a.flags || [])]
                .some(campo => (campo || '').toLowerCase().includes(texto))
        })
    }, [alertas, filtro, busqueda])

    const conteoFiltro = (id) => id === 'todos'
        ? alertas.length
        : estadisticas[id]

    const verEnMapa = (alerta) => {
        if (!tieneCoordenadas(alerta)) return
        setSeleccionado(alerta.id)
        seccionMapa.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }

    const porcentaje = (n) => estadisticas.total ? (n / estadisticas.total) * 100 : 0

    return (
        <div className="dashboard">
            <section className="hero">
                <div className="hero-texto">
                    <span className="eyebrow">
                        <span className={`punto-vivo ${errorConexion ? 'desconectado' : ''}`} />
                        {errorConexion
                            ? 'Sin conexión con la base de datos'
                            : cargando
                                ? 'Conectando…'
                                : desdeCache
                                    ? 'Mostrando datos guardados · sincronizando…'
                                    : `En vivo · actualizado ${tiempoRelativo(actualizado, ahora)}`}
                    </span>
                    <h1>Panel de inteligencia territorial</h1>
                    <p>
                        Cada mensaje sospechoso que reporta un vecino se analiza, se sella con un
                        certificado y aparece aquí al instante. Así vemos dónde se mueve el fraude en Bosa.
                    </p>
                </div>
                <Link to="/reportar" className="boton boton-primario boton-grande">
                    <Icono nombre="bandera" /> Reportar mensaje sospechoso <Icono nombre="flecha" className="icono-flecha" />
                </Link>
            </section>

            <section className="tarjetas-estadisticas">
                <TarjetaEstadistica icono="capas" valor={estadisticas.total} etiqueta="Reportes en el mapa"
                    detalle={`${estadisticas.ultimas24h} en las últimas 24 h`} />
                <TarjetaEstadistica icono="alerta" variante="alto" valor={estadisticas.alto} etiqueta="Riesgo alto"
                    detalle={`${Math.round(porcentaje(estadisticas.alto))}% del total`} />
                <TarjetaEstadistica icono="pulso" variante="medio" valor={estadisticas.medio} etiqueta="Riesgo medio"
                    detalle={`${Math.round(porcentaje(estadisticas.medio))}% del total`} />
                <TarjetaEstadistica icono="escudo" variante="bajo" valor={estadisticas.promedio} sufijo="%" etiqueta="Riesgo promedio"
                    detalle={nivelRiesgo(estadisticas.promedio).etiqueta + ' en promedio'} />
            </section>

            <section className="rejilla-mapa" ref={seccionMapa}>
                <div className="panel panel-mapa">
                    <div className="panel-cabecera">
                        <h2>Mapa de calor</h2>
                        <span className="texto-suave">Toca un punto o un reporte para ver el detalle</span>
                    </div>
                    {/* El mapa se monta de inmediato; los puntos aparecen cuando llega Firestore */}
                    <MapaCalor
                        reportes={alertas}
                        cargando={cargando}
                        seleccionadoId={seleccionado}
                        onSeleccionar={setSeleccionado}
                    />
                </div>

                <aside className="columna-lateral">
                    <div className="panel">
                        <div className="panel-cabecera"><h2>Distribución del riesgo</h2></div>
                        <div className="barra-distribucion" role="img"
                            aria-label={`Alto ${estadisticas.alto}, medio ${estadisticas.medio}, bajo ${estadisticas.bajo}`}>
                            <span className="fondo-alto" style={{ flexGrow: estadisticas.alto }} />
                            <span className="fondo-medio" style={{ flexGrow: estadisticas.medio }} />
                            <span className="fondo-bajo" style={{ flexGrow: estadisticas.bajo || (estadisticas.total ? 0 : 1) }} />
                        </div>
                        <ul className="leyenda-distribucion">
                            {[['alto', 'Alto', estadisticas.alto], ['medio', 'Medio', estadisticas.medio], ['bajo', 'Bajo', estadisticas.bajo]]
                                .map(([id, etiqueta, n]) => (
                                    <li key={id}>
                                        <i className={`punto-leyenda fondo-${id}`} />
                                        <span>{etiqueta}</span>
                                        <strong>{n}</strong>
                                    </li>
                                ))}
                        </ul>
                    </div>

                    <div className="panel">
                        <div className="panel-cabecera"><h2>Reportes por UPZ</h2></div>
                        <ol className="ranking-upz">
                            {rankingUpz.map((u, i) => (
                                <li key={u.id} style={{ '--retraso': `${i * 70}ms` }}>
                                    <div className="ranking-fila">
                                        <span><span className="ranking-codigo">{u.codigo}</span> {u.nombre}</span>
                                        <strong>{u.total}</strong>
                                    </div>
                                    <div className="ranking-pista">
                                        <span style={{ transform: `scaleX(${u.proporcion})` }} />
                                    </div>
                                    {u.alto > 0 && <small className="texto-alto">{u.alto} de riesgo alto</small>}
                                </li>
                            ))}
                        </ol>
                    </div>
                </aside>
            </section>

            <section className="seccion-reportes">
                <div className="barra-herramientas">
                    <h2>Últimos reportes</h2>
                    <div className="controles">
                        <div className="segmentado" role="tablist" aria-label="Filtrar por nivel de riesgo">
                            {FILTROS.map(f => (
                                <button
                                    key={f.id}
                                    type="button"
                                    role="tab"
                                    aria-selected={filtro === f.id}
                                    className={`segmento ${filtro === f.id ? 'activo' : ''} ${f.id !== 'todos' ? `segmento-${f.id}` : ''}`}
                                    onClick={() => { setFiltro(f.id); setVisibles(POR_PAGINA) }}
                                >
                                    {f.etiqueta} <span className="segmento-conteo">{conteoFiltro(f.id)}</span>
                                </button>
                            ))}
                        </div>
                        <label className="buscador">
                            <Icono nombre="buscar" tamano={16} />
                            <input
                                type="search"
                                placeholder="Buscar texto, UPZ o señal…"
                                value={busqueda}
                                onChange={e => { setBusqueda(e.target.value); setVisibles(POR_PAGINA) }}
                            />
                        </label>
                    </div>
                </div>

                {cargando ? (
                    <div className="lista-reportes">
                        {[0, 1, 2, 3].map(i => <div key={i} className="tarjeta-reporte esqueleto esqueleto-tarjeta" />)}
                    </div>
                ) : filtradas.length === 0 ? (
                    <div className="estado-vacio">
                        <Icono nombre={alertas.length ? 'buscar' : 'escudo'} tamano={32} />
                        <p>{alertas.length ? 'Ningún reporte coincide con tu búsqueda.' : 'Aún no hay reportes. Sé el primero en reportar.'}</p>
                        {alertas.length === 0 && <Link to="/reportar" className="boton boton-secundario">Hacer un reporte</Link>}
                    </div>
                ) : (
                    <>
                        <div className="lista-reportes">
                            {filtradas.slice(0, visibles).map((alerta, i) => {
                                const { etiqueta, clase, id } = nivelRiesgo(alerta.nivel_riesgo)
                                const enMapa = tieneCoordenadas(alerta)
                                return (
                                    <article
                                        key={alerta.id}
                                        className={`tarjeta-reporte ${clase} ${nuevos.has(alerta.id) ? 'entrante' : ''} ${seleccionado === alerta.id ? 'seleccionada' : ''} ${enMapa ? 'interactiva' : ''}`}
                                        style={{ '--retraso': `${Math.min(i, 8) * 45}ms` }}
                                        onClick={() => verEnMapa(alerta)}
                                        tabIndex={enMapa ? 0 : undefined}
                                        onKeyDown={e => e.key === 'Enter' && verEnMapa(alerta)}
                                    >
                                        <div className="reporte-cabecera">
                                            <span className={`chip chip-${id}`}>
                                                <i className={`punto-leyenda fondo-${id}`} /> {etiqueta} · {alerta.nivel_riesgo}%
                                            </span>
                                            {nuevos.has(alerta.id) && <span className="etiqueta-nuevo">Nuevo</span>}
                                            <span className="reporte-tiempo" title={new Date(alerta.fecha).toLocaleString('es-CO')}>
                                                {tiempoRelativo(alerta.fecha, ahora)}
                                            </span>
                                        </div>

                                        <div className="medidor-lineal" aria-hidden="true">
                                            <span className={`fondo-${id}`} style={{ width: `${alerta.nivel_riesgo || 0}%` }} />
                                        </div>

                                        <p className="reporte-mensaje">“{alerta.mensaje_original}”</p>

                                        {alerta.flags?.length > 0 && (
                                            <div className="flags">
                                                {alerta.flags.map(flag => <span key={flag} className="flag">{flag}</span>)}
                                            </div>
                                        )}

                                        {alerta.verificacion?.hallazgos?.length > 0 && (
                                            <p className="hallazgo">
                                                <Icono nombre="buscar" tamano={15} />
                                                <span>
                                                    <strong>Cruce de fuentes:</strong> {alerta.verificacion.hallazgos[0].detalle}
                                                    {' '}({alerta.verificacion.hallazgos[0].valor})
                                                </span>
                                            </p>
                                        )}

                                        <div className="reporte-pie">
                                            <span><Icono nombre="pin" tamano={14} /> UPZ {alerta.upz || alerta.barrio || 'Bosa'}</span>
                                            <span><Icono nombre="mensaje" tamano={14} /> {alerta.canal || 'whatsapp'}</span>
                                            {alerta.adjuntos?.length > 0 && (
                                                <span><Icono nombre="clip" tamano={14} /> {alerta.adjuntos.length}</span>
                                            )}
                                            <span className="certificado"><Icono nombre="hash" tamano={14} />{(alerta.certificado || '').slice(0, 10)}</span>
                                            {enMapa && <span className="ver-mapa">Ver en mapa <Icono nombre="flecha" tamano={14} /></span>}
                                        </div>
                                    </article>
                                )
                            })}
                        </div>
                        {visibles < filtradas.length && (
                            <button type="button" className="boton boton-secundario boton-mas" onClick={() => setVisibles(v => v + POR_PAGINA)}>
                                Mostrar más ({filtradas.length - visibles} restantes)
                            </button>
                        )}
                    </>
                )}
            </section>
        </div>
    )
}
