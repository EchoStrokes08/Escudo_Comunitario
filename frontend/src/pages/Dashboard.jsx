import { useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import MapaCalor, { tieneCoordenadas } from '../components/MapaCalor.jsx'
import { useAlertas, useAlertasComunitarias } from '../services/alertas.js'
import Icono from '../components/Icono.jsx'
import GraficaTendencia from '../components/GraficaTendencia.jsx'
import { nivelConfianza, nivelRiesgo, nombreTipo } from '../utils/riesgo.js'
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

const TIPO_INDICADOR = { dominio: 'Enlace', cuenta: 'Cuenta', telefono: 'Celular' }

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
    const alertasComunidad = useAlertasComunitarias()
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
        let sumaConfianza = 0
        let ultimas24h = 0
        let certificados = 0
        for (const a of alertas) {
            conteo[a.nivel] += 1
            suma += a.nivel_riesgo
            sumaConfianza += a.confianza
            if (a.certificado) certificados += 1
            if (a.fecha && ahora - new Date(a.fecha).getTime() < 86_400_000) ultimas24h += 1
        }
        const total = alertas.length
        return {
            total, ...conteo, ultimas24h, certificados,
            promedio: total ? Math.round(suma / total) : 0,
            confianza: total ? Math.round(sumaConfianza / total) : 0,
        }
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

    // Inteligencia: qué tipos de fraude, qué entidades suplantan y qué cuentas/dominios se repiten
    const inteligencia = useMemo(() => {
        const tipos = {}
        const entidades = {}
        const indicadores = {}
        for (const a of alertas) {
            if (a.nivel !== 'bajo' && a.tipo_fraude !== 'legitimo') tipos[a.tipo_fraude] = (tipos[a.tipo_fraude] || 0) + 1
            const entidad = (a.entidad_suplantada || '').trim()
            if (entidad) entidades[entidad] = (entidades[entidad] || 0) + 1
            for (const ind of a.indicadores) {
                const clave = `${ind.tipo}|${ind.valor}`
                indicadores[clave] = indicadores[clave] || { ...ind, veces: 0 }
                indicadores[clave].veces += 1
            }
        }
        const orden = (obj) => Object.entries(obj).sort((x, y) => y[1] - x[1])
        const filasTipos = orden(tipos).slice(0, 6)
        const maxTipo = Math.max(1, ...filasTipos.map(([, n]) => n))
        return {
            tipos: filasTipos.map(([id, n]) => ({ id, nombre: nombreTipo(id), n, proporcion: n / maxTipo })),
            entidades: orden(entidades).slice(0, 8),
            indicadores: Object.values(indicadores).sort((x, y) => y.veces - x.veces).slice(0, 6),
        }
    }, [alertas])

    const filtradas = useMemo(() => {
        const texto = busqueda.trim().toLowerCase()
        return alertas.filter(a => {
            if (filtro !== 'todos' && a.nivel !== filtro) return false
            if (!texto) return true
            return [a.mensaje_anonimizado, a.upz, nombreTipo(a.tipo_fraude), a.entidad_suplantada, a.certificado, ...(a.flags || [])]
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
                        Cada mensaje sospechoso que reporta un vecino se analiza con IA, se verifica en fuentes
                        abiertas, se sella con un certificado inmutable y aparece aquí al instante, sin datos personales.
                    </p>
                </div>
                <Link to="/reportar" className="boton boton-primario boton-grande">
                    <Icono nombre="bandera" /> Reportar mensaje sospechoso <Icono nombre="flecha" className="icono-flecha" />
                </Link>
            </section>

            {alertasComunidad.length > 0 && (
                <section className="alertas-comunidad" aria-live="polite">
                    {alertasComunidad.slice(0, 3).map(alerta => (
                        <div key={alerta.id} className="alerta-comunidad">
                            <span className="alerta-icono"><Icono nombre="campana" tamano={18} /></span>
                            <div>
                                <strong>Alerta temprana · UPZ {alerta.upz}</strong>
                                <span>{alerta.casos} casos de {(alerta.nombre_tipo || nombreTipo(alerta.tipo_fraude)).toLowerCase()} en {alerta.ventana_horas} h
                                    {alerta.lideres_notificados > 0 && ` · ${alerta.lideres_notificados} líderes avisados por WhatsApp`}</span>
                            </div>
                            <span className="reporte-tiempo">{tiempoRelativo(alerta.fecha, ahora)}</span>
                        </div>
                    ))}
                </section>
            )}

            <section className="tarjetas-estadisticas">
                <TarjetaEstadistica icono="capas" valor={estadisticas.total} etiqueta="Reportes en el mapa"
                    detalle={`${estadisticas.ultimas24h} en las últimas 24 h`} />
                <TarjetaEstadistica icono="alerta" variante="alto" valor={estadisticas.alto} etiqueta="Riesgo alto"
                    detalle={`${Math.round(porcentaje(estadisticas.alto))}% del total`} />
                <TarjetaEstadistica icono="pulso" variante="medio" valor={estadisticas.medio} etiqueta="Riesgo medio"
                    detalle={`${Math.round(porcentaje(estadisticas.medio))}% del total`} />
                <TarjetaEstadistica icono="escudo" variante="bajo" valor={estadisticas.confianza} sufijo="%" etiqueta="Confianza promedio"
                    detalle={`Riesgo promedio ${estadisticas.promedio}% · confianza ${nivelConfianza(estadisticas.confianza).etiqueta.toLowerCase()}`} />
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

                    <Link to="/verificar" className="panel panel-registro">
                        <span className="registro-icono"><Icono nombre="cadena" tamano={20} /></span>
                        <div>
                            <strong>{estadisticas.certificados} certificados encadenados</strong>
                            <span>Cada reporte queda sellado en una cadena de hashes anclada en Bitcoin. Audítala →</span>
                        </div>
                    </Link>

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

            <section className="rejilla-inteligencia">
                <div className="panel">
                    <div className="panel-cabecera">
                        <h2>Tendencia</h2>
                        <span className="texto-suave">Últimos 14 días</span>
                    </div>
                    <GraficaTendencia reportes={alertas} ahora={ahora} />
                </div>

                <div className="panel">
                    <div className="panel-cabecera"><h2>Tipos de fraude</h2><span className="texto-suave">Riesgo medio o alto</span></div>
                    {inteligencia.tipos.length === 0
                        ? <p className="texto-suave">Aún no hay suficientes reportes.</p>
                        : (
                            <ol className="ranking-upz ranking-tipos">
                                {inteligencia.tipos.map(t => (
                                    <li key={t.id}>
                                        <div className="ranking-fila"><span>{t.nombre}</span><strong>{t.n}</strong></div>
                                        <div className="ranking-pista"><span style={{ transform: `scaleX(${t.proporcion})` }} /></div>
                                    </li>
                                ))}
                            </ol>
                        )}
                    {inteligencia.entidades.length > 0 && (
                        <>
                            <h3 className="subtitulo-panel">Entidades más suplantadas</h3>
                            <div className="flags">
                                {inteligencia.entidades.map(([nombre, n]) => <span key={nombre} className="flag">{nombre} · {n}</span>)}
                            </div>
                        </>
                    )}
                </div>

                <div className="panel">
                    <div className="panel-cabecera"><h2>Lo más reportado</h2><span className="texto-suave">Cuentas, números y enlaces</span></div>
                    {inteligencia.indicadores.length === 0
                        ? <p className="texto-suave">Cuando los vecinos reporten cuentas o enlaces, aparecerán aquí.</p>
                        : (
                            <table className="tabla-indicadores">
                                <thead><tr><th>Indicador</th><th>Tipo</th><th>Reportes</th></tr></thead>
                                <tbody>
                                    {inteligencia.indicadores.map(i => (
                                        <tr key={`${i.tipo}|${i.valor}`}>
                                            <td className="mono">{i.valor}</td>
                                            <td>{TIPO_INDICADOR[i.tipo] || i.tipo}</td>
                                            <td><strong>{i.veces}</strong></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    <p className="nota-privacidad"><Icono nombre="candado" tamano={13} /> Datos anonimizados: números enmascarados, enlaces desactivados y ubicación generalizada a ~200 m.</p>
                </div>
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
                                            {alerta.tipo_fraude !== 'legitimo' && id !== 'bajo' && <span className="chip chip-neutro">{nombreTipo(alerta.tipo_fraude)}</span>}
                                            {nuevos.has(alerta.id) && <span className="etiqueta-nuevo">Nuevo</span>}
                                            <span className="reporte-tiempo" title={new Date(alerta.fecha).toLocaleString('es-CO')}>
                                                {tiempoRelativo(alerta.fecha, ahora)}
                                            </span>
                                        </div>

                                        <div className="medidor-lineal" aria-hidden="true">
                                            <span className={`fondo-${id}`} style={{ width: `${alerta.nivel_riesgo || 0}%` }} />
                                        </div>

                                        <p className="reporte-mensaje">“{alerta.mensaje_anonimizado || 'Reporte con archivo adjunto o nota de voz'}”</p>

                                        {alerta.flags?.length > 0 && (
                                            <div className="flags">
                                                {alerta.flags.map(flag => <span key={flag} className="flag">{flag}</span>)}
                                            </div>
                                        )}

                                        {alerta.hallazgos.length > 0 && (
                                            <p className="hallazgo">
                                                <Icono nombre="buscar" tamano={15} />
                                                <span>
                                                    <strong>Verificado:</strong> {alerta.hallazgos[0].detalle}
                                                    {' '}({alerta.hallazgos[0].valor})
                                                </span>
                                            </p>
                                        )}

                                        <div className="reporte-pie">
                                            <span><Icono nombre="pin" tamano={14} /> {alerta.upz ? `UPZ ${alerta.upz}` : 'UPZ por confirmar'}</span>
                                            <span><Icono nombre={alerta.con_audio ? 'microfono' : 'mensaje'} tamano={14} /> {alerta.canal || 'whatsapp'}</span>
                                            {alerta.confianza > 0 && <span title="Confianza del análisis"><Icono nombre="escudo" tamano={14} /> {alerta.confianza}%</span>}
                                            {alerta.adjuntos?.length > 0 && (
                                                <span><Icono nombre="clip" tamano={14} /> {alerta.adjuntos.length}</span>
                                            )}
                                            {alerta.certificado && (
                                                <Link to={`/verificar/${alerta.certificado}`} className="certificado" onClick={e => e.stopPropagation()} title="Verificar certificado">
                                                    <Icono nombre="hash" tamano={14} />{alerta.certificado.slice(0, 10)}
                                                </Link>
                                            )}
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
