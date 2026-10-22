import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Icono from '../components/Icono.jsx'
import LineaTiempo from '../components/LineaTiempo.jsx'
import {
    API_URL, cambiarEstadoCaso, casosAgrupados, casosAutoridades, descargarArchivo, exportarCasosCsv,
    paqueteEvidencia, resumenAutoridades,
} from '../services/api.js'
import { nivelRiesgo, nombreTipo } from '../utils/riesgo.js'
import { ESTADOS_CASO, etiquetaEstado } from '../utils/estados.js'

const CLAVE_SESION = 'escudo-token-autoridades'
const CLAVE_ACTOR = 'escudo-actor-autoridades'

function leer(clave, almacen = 'sessionStorage') {
    try { return window[almacen].getItem(clave) || '' } catch { return '' }
}
function guardar(clave, valor, almacen = 'sessionStorage') {
    try { valor ? window[almacen].setItem(clave, valor) : window[almacen].removeItem(clave) } catch { /* sin almacenamiento */ }
}

const ETIQUETA_INDICADOR = { dominio: 'Dominio', cuenta: 'Cuenta', telefono: 'Teléfono' }

/** Formulario para pasar un caso al siguiente estado: genera un bloque nuevo en la cadena. */
function CambiarEstado({ caso, token, onListo, onCancelar }) {
    const actual = caso.estado || 'registrado'
    const opciones = Object.entries(ESTADOS_CASO).filter(([id]) => id !== 'registrado' && id !== actual)
    const [estado, setEstado] = useState(opciones[0]?.[0] || '')
    const [actor, setActor] = useState(() => leer(CLAVE_ACTOR, 'localStorage'))
    const [nota, setNota] = useState('')
    const [enviando, setEnviando] = useState(false)
    const [error, setError] = useState(null)

    const enviar = async (e) => {
        e.preventDefault()
        setEnviando(true)
        setError(null)
        try {
            const r = await cambiarEstadoCaso(token, caso.certificado, { estado, actor: actor.trim(), nota: nota.trim() })
            guardar(CLAVE_ACTOR, actor.trim(), 'localStorage')
            onListo(caso.id, estado, r)
        } catch (err) {
            setError(err.message)
        } finally {
            setEnviando(false)
        }
    }

    return (
        <form className="cambio-estado" onSubmit={enviar}>
            <div className="cambio-estado-campos">
                <label>Nuevo estado
                    <select value={estado} onChange={e => setEstado(e.target.value)}>
                        {opciones.map(([id, { etiqueta }]) => <option key={id} value={id}>{etiqueta}</option>)}
                    </select>
                </label>
                <label>Quién actúa
                    <input value={actor} onChange={e => setActor(e.target.value)} placeholder="Ej. CAI Bosa Centro" required minLength={2} maxLength={80} />
                </label>
            </div>
            <label>Mensaje para la víctima <span className="texto-suave">(opcional, público)</span>
                <textarea rows={2} value={nota} onChange={e => setNota(e.target.value)} maxLength={500}
                    placeholder="Ej. Su caso fue remitido a la Fiscalía Seccional Bogotá con el radicado…" />
            </label>
            <p className="nota-privacidad">
                <Icono nombre="candado" tamano={12} />
                El cambio queda encadenado y sellado en Bitcoin. El mensaje se publica en la página de verificación (los números se enmascaran)
                y, si la víctima lo pidió, le llega por WhatsApp o Telegram.
            </p>
            {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}
            <div className="controles">
                <button className="boton boton-primario" disabled={enviando || !estado || actor.trim().length < 2}>
                    {enviando ? <><span className="spinner" /> Registrando…</> : <><Icono nombre="cadena" /> Registrar en la cadena</>}
                </button>
                <button type="button" className="boton-texto" onClick={onCancelar}>Cancelar</button>
            </div>
        </form>
    )
}

function TablaCasos({ casos, token, onActualizado }) {
    const [filtro, setFiltro] = useState('')
    const [estadoFiltro, setEstadoFiltro] = useState('todos')
    const [abierto, setAbierto] = useState(null)
    const [lineas, setLineas] = useState({})

    const filtrados = useMemo(() => {
        const t = filtro.trim().toLowerCase()
        return casos.filter(c => (estadoFiltro === 'todos' || (c.estado || 'registrado') === estadoFiltro)
            && (!t || JSON.stringify([c.mensaje_original, c.indicadores, c.upz, c.tipo_fraude, c.certificado]).toLowerCase().includes(t)))
    }, [casos, filtro, estadoFiltro])

    const listo = (id, estado, respuesta) => {
        setLineas(l => ({ ...l, [id]: respuesta.seguimiento }))
        onActualizado(id, estado)
    }

    return (
        <>
            <div className="barra-herramientas">
                <h2>{filtrados.length} de {casos.length} casos</h2>
                <div className="controles">
                    <select className="selector-compacto" value={estadoFiltro} onChange={e => setEstadoFiltro(e.target.value)} aria-label="Filtrar por estado">
                        <option value="todos">Todos los estados</option>
                        {Object.entries(ESTADOS_CASO).map(([id, { etiqueta }]) => <option key={id} value={id}>{etiqueta}</option>)}
                    </select>
                    <label className="buscador">
                        <Icono nombre="buscar" tamano={16} />
                        <input type="search" placeholder="Buscar cuenta, dominio, UPZ…" value={filtro} onChange={e => setFiltro(e.target.value)} />
                    </label>
                </div>
            </div>
            <div className="tabla-envoltura">
                <table className="tabla-casos">
                    <thead>
                        <tr><th>Fecha</th><th>Riesgo</th><th>Tipo</th><th>UPZ</th><th>Indicadores</th><th>Mensaje</th><th>Estado</th><th>Certificado</th></tr>
                    </thead>
                    <tbody>
                        {filtrados.map(c => {
                            const nivel = nivelRiesgo(c.nivel_riesgo)
                            const estado = c.estado || 'registrado'
                            return (
                                <Fragment key={c.id}>
                                    <tr>
                                        <td>{c.fecha ? new Date(c.fecha).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</td>
                                        <td><span className={`chip chip-${nivel.id}`}>{c.nivel_riesgo}%</span></td>
                                        <td>{nombreTipo(c.tipo_fraude)}</td>
                                        <td>{c.upz || '—'}</td>
                                        <td className="mono">{(c.indicadores || []).map(i => i.valor).join(', ') || '—'}</td>
                                        <td className="celda-mensaje">{c.mensaje_original || c.texto_detectado || '—'}</td>
                                        <td>
                                            <span className={`chip chip-estado estado-${estado}`}>{etiquetaEstado(estado)}</span>
                                            {c.certificado && estado !== 'cerrado' && (
                                                <button type="button" className="boton-texto" onClick={() => setAbierto(abierto === c.id ? null : c.id)}>
                                                    <Icono nombre="flecha" tamano={13} /> Actualizar
                                                </button>
                                            )}
                                        </td>
                                        <td>{c.certificado
                                            ? <Link className="mono" to={`/verificar/${c.certificado}`}>{c.certificado.slice(0, 10)}…</Link>
                                            : <span className="texto-suave">legado</span>}</td>
                                    </tr>
                                    {(abierto === c.id || lineas[c.id]) && (
                                        <tr className="fila-detalle">
                                            <td colSpan={8}>
                                                {lineas[c.id] && <LineaTiempo eventos={lineas[c.id]} compacta />}
                                                {abierto === c.id && (
                                                    <CambiarEstado caso={c} token={token} onCancelar={() => setAbierto(null)}
                                                        onListo={(...args) => { listo(...args); setAbierto(null) }} />
                                                )}
                                            </td>
                                        </tr>
                                    )}
                                </Fragment>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </>
    )
}

/** Un mismo dominio, cuenta o teléfono reportado por varias personas: un caso con varias víctimas. */
function Agrupados({ token }) {
    const [grupos, setGrupos] = useState(null)
    const [error, setError] = useState(null)
    const [descargando, setDescargando] = useState(null)

    useEffect(() => {
        let vigente = true
        casosAgrupados(token).then(d => vigente && setGrupos(d.grupos)).catch(e => vigente && setError(e.message))
        return () => { vigente = false }
    }, [token])

    const descargar = async (g) => {
        setDescargando(g.id)
        try {
            const paquete = await paqueteEvidencia(token, g.id)
            descargarArchivo(paquete, `evidencia-${g.tipo}-${String(g.valor).replace(/[^\w.-]/g, '').slice(0, 24)}.json`)
        } catch (e) {
            setError(e.message)
        } finally {
            setDescargando(null)
        }
    }

    if (error) return <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>
    if (!grupos) return <div className="cargando-pagina"><span className="spinner" /></div>
    if (!grupos.length) return <p className="estado-vacio">Aún no hay dominios, cuentas ni teléfonos reportados por más de una persona.</p>

    return (
        <>
            <p className="texto-suave">
                Indicadores reportados por varias personas, de mayor a menor. Cada paquete de evidencia reúne todos los casos
                con sus mensajes originales, las fuentes consultadas y el certificado verificable de cada reporte.
            </p>
            <div className="tabla-envoltura">
                <table className="tabla-casos tabla-agrupados">
                    <thead><tr><th>Indicador</th><th>Reportes</th><th>UPZ</th><th>Último reporte</th><th>Evidencia</th></tr></thead>
                    <tbody>
                        {grupos.map(g => (
                            <tr key={g.id}>
                                <td><span className="texto-suave">{ETIQUETA_INDICADOR[g.tipo] || g.tipo}</span><br /><strong className="mono">{g.valor}</strong></td>
                                <td><span className={`chip ${g.veces >= 5 ? 'chip-alto' : 'chip-medio'}`}>{g.veces} {g.veces === 1 ? 'víctima' : 'víctimas'}</span></td>
                                <td>{g.upz.join(', ') || '—'}</td>
                                <td>{g.ultima ? new Date(g.ultima).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</td>
                                <td>
                                    <button type="button" className="boton boton-secundario boton-compacto" onClick={() => descargar(g)} disabled={descargando === g.id}>
                                        {descargando === g.id ? <span className="spinner" /> : <Icono nombre="descargar" tamano={15} />} Paquete de evidencia
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </>
    )
}

function Resumen({ resumen }) {
    if (!resumen) return null
    const por = resumen.por_estado || {}
    const retro = resumen.retroalimentacion || {}
    const tarjetas = [
        { icono: 'archivo', valor: resumen.casos, texto: 'Casos registrados' },
        { icono: 'buscar', valor: (por.en_revision || 0) + (por.en_investigacion || 0), texto: 'En revisión o investigación' },
        { icono: 'flecha', valor: por.remitido || 0, texto: 'Remitidos a Policía / Fiscalía' },
        { icono: 'check', valor: por.cerrado || 0, texto: 'Cerrados' },
        { icono: 'usuarios', valor: retro.util_pct != null ? `${retro.util_pct}%` : '—', texto: `Le sirvió a la gente (${retro.respuestas || 0} opiniones)` },
    ]
    return (
        <div className="resumen-autoridades">
            {tarjetas.map(t => (
                <div key={t.texto} className="resumen-tarjeta">
                    <Icono nombre={t.icono} tamano={16} />
                    <strong>{t.valor}</strong>
                    <span>{t.texto}</span>
                </div>
            ))}
        </div>
    )
}

/** Vista restringida para Policía, Fiscalía y organizaciones: casos, seguimiento, agrupación y evidencia. */
export default function Autoridades() {
    const [token, setToken] = useState(() => leer(CLAVE_SESION))
    const [entrada, setEntrada] = useState('')
    const [casos, setCasos] = useState(null)
    const [resumen, setResumen] = useState(null)
    const [pestana, setPestana] = useState('casos')
    const [error, setError] = useState(null)
    const [cargando, setCargando] = useState(false)

    const cargar = async (clave = token) => {
        setCargando(true)
        setError(null)
        try {
            const [datos, res] = await Promise.all([casosAutoridades(clave), resumenAutoridades(clave).catch(() => null)])
            setCasos(datos.casos)
            setResumen(res)
            setToken(clave)
            guardar(CLAVE_SESION, clave)
        } catch (e) {
            setError(e.status === 401 ? 'Token inválido.' : e.message)
            setCasos(null)
        } finally {
            setCargando(false)
        }
    }

    const exportar = async () => descargarArchivo(await exportarCasosCsv(token), 'casos-escudo-comunitario.csv')

    const salir = () => {
        guardar(CLAVE_SESION, '')
        setToken('')
        setCasos(null)
    }

    const actualizado = (id, estado) => {
        setCasos(cs => cs.map(c => (c.id === id ? { ...c, estado } : c)))
        resumenAutoridades(token).then(setResumen).catch(() => {})
    }

    return (
        <div className="pagina-autoridades">
            <section className="hero hero-compacto">
                <div className="hero-texto">
                    <span className="eyebrow"><Icono nombre="candado" tamano={14} /> Acceso restringido</span>
                    <h1>Vista para autoridades</h1>
                    <p>
                        Casos completos con mensajes originales, cuentas y dominios sin enmascarar y su certificado verificable.
                        Cada cambio de estado queda encadenado y la víctima puede seguirlo. El teléfono de las víctimas nunca se almacena.
                    </p>
                </div>
            </section>

            {!casos ? (
                <form className="panel acceso-autoridades" onSubmit={e => { e.preventDefault(); cargar(entrada.trim()) }}>
                    <label htmlFor="token">Token de acceso</label>
                    <input id="token" type="password" value={entrada} onChange={e => setEntrada(e.target.value)} autoComplete="off" />
                    <button className="boton boton-primario" disabled={!entrada.trim() || cargando}>
                        {cargando ? <><span className="spinner" /> Validando…</> : <><Icono nombre="candado" /> Ingresar</>}
                    </button>
                    {token && !cargando && <button type="button" className="boton-texto" onClick={() => cargar()}>Usar la sesión guardada</button>}
                    {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}
                </form>
            ) : (
                <section className="seccion-reportes">
                    <Resumen resumen={resumen} />
                    <div className="barra-herramientas">
                        <div className="segmentado" role="tablist">
                            <button type="button" role="tab" aria-selected={pestana === 'casos'} className={`segmento ${pestana === 'casos' ? 'activo' : ''}`} onClick={() => setPestana('casos')}>
                                <Icono nombre="archivo" tamano={14} /> Casos
                            </button>
                            <button type="button" role="tab" aria-selected={pestana === 'agrupados'} className={`segmento ${pestana === 'agrupados' ? 'activo' : ''}`} onClick={() => setPestana('agrupados')}>
                                <Icono nombre="usuarios" tamano={14} /> Agrupados por indicador
                            </button>
                        </div>
                        <div className="controles">
                            <button type="button" className="boton boton-secundario" onClick={exportar}><Icono nombre="descargar" /> Exportar CSV</button>
                            <button type="button" className="boton-texto" onClick={salir}>Salir</button>
                        </div>
                    </div>
                    {pestana === 'casos'
                        ? <TablaCasos casos={casos} token={token} onActualizado={actualizado} />
                        : <Agrupados token={token} />}
                    <p className="texto-suave">Fuente: {API_URL || window.location.origin}/api/autoridades</p>
                </section>
            )}
        </div>
    )
}
