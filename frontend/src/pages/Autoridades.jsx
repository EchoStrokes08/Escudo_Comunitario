import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Icono from '../components/Icono.jsx'
import { API_URL, pedir } from '../services/api.js'
import { nivelRiesgo, nombreTipo } from '../utils/riesgo.js'

const CLAVE_SESION = 'escudo-token-autoridades'

function leerToken() {
    try { return sessionStorage.getItem(CLAVE_SESION) || '' } catch { return '' }
}

/** Vista restringida para Policía, Fiscalía y organizaciones: casos completos y exportación CSV. */
export default function Autoridades() {
    const [token, setToken] = useState(leerToken)
    const [entrada, setEntrada] = useState('')
    const [casos, setCasos] = useState(null)
    const [error, setError] = useState(null)
    const [cargando, setCargando] = useState(false)
    const [filtro, setFiltro] = useState('')

    const cargar = async (clave = token) => {
        setCargando(true)
        setError(null)
        try {
            const datos = await pedir('/api/autoridades/casos', { headers: { Authorization: `Bearer ${clave}` } })
            setCasos(datos.casos)
            setToken(clave)
            try { sessionStorage.setItem(CLAVE_SESION, clave) } catch { /* sin almacenamiento */ }
        } catch (e) {
            setError(e.status === 401 ? 'Token inválido.' : e.message)
            setCasos(null)
        } finally {
            setCargando(false)
        }
    }

    const exportar = async () => {
        const blob = await pedir('/api/autoridades/casos?formato=csv', { headers: { Authorization: `Bearer ${token}` } })
        const url = URL.createObjectURL(blob)
        const a = Object.assign(document.createElement('a'), { href: url, download: 'casos-escudo-comunitario.csv' })
        a.click()
        URL.revokeObjectURL(url)
    }

    const salir = () => {
        try { sessionStorage.removeItem(CLAVE_SESION) } catch { /* sin almacenamiento */ }
        setToken('')
        setCasos(null)
    }

    const filtrados = useMemo(() => {
        const t = filtro.trim().toLowerCase()
        if (!casos || !t) return casos || []
        return casos.filter(c => JSON.stringify([c.mensaje_original, c.indicadores, c.upz, c.tipo_fraude, c.certificado]).toLowerCase().includes(t))
    }, [casos, filtro])

    return (
        <div className="pagina-autoridades">
            <section className="hero hero-compacto">
                <div className="hero-texto">
                    <span className="eyebrow"><Icono nombre="candado" tamano={14} /> Acceso restringido</span>
                    <h1>Vista para autoridades</h1>
                    <p>
                        Casos completos con mensajes originales, cuentas y dominios sin enmascarar y su certificado verificable,
                        para actuar de forma coordinada. El teléfono de las víctimas nunca se almacena.
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
                    <div className="barra-herramientas">
                        <h2>{casos.length} casos</h2>
                        <div className="controles">
                            <label className="buscador">
                                <Icono nombre="buscar" tamano={16} />
                                <input type="search" placeholder="Buscar cuenta, dominio, UPZ…" value={filtro} onChange={e => setFiltro(e.target.value)} />
                            </label>
                            <button type="button" className="boton boton-secundario" onClick={exportar}><Icono nombre="descargar" /> Exportar CSV</button>
                            <button type="button" className="boton-texto" onClick={salir}>Salir</button>
                        </div>
                    </div>
                    <div className="tabla-envoltura">
                        <table className="tabla-casos">
                            <thead>
                                <tr><th>Fecha</th><th>Riesgo</th><th>Tipo</th><th>UPZ</th><th>Indicadores</th><th>Mensaje</th><th>Certificado</th></tr>
                            </thead>
                            <tbody>
                                {filtrados.map(c => {
                                    const nivel = nivelRiesgo(c.nivel_riesgo)
                                    return (
                                        <tr key={c.id}>
                                            <td>{c.fecha ? new Date(c.fecha).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) : '—'}</td>
                                            <td><span className={`chip chip-${nivel.id}`}>{c.nivel_riesgo}%</span></td>
                                            <td>{nombreTipo(c.tipo_fraude)}</td>
                                            <td>{c.upz || '—'}</td>
                                            <td className="mono">{(c.indicadores || []).map(i => i.valor).join(', ') || '—'}</td>
                                            <td className="celda-mensaje">{c.mensaje_original || c.texto_detectado || '—'}</td>
                                            <td>{c.certificado
                                                ? <Link className="mono" to={`/verificar/${c.certificado}`}>{c.certificado.slice(0, 10)}…</Link>
                                                : <span className="texto-suave">legado</span>}</td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                    <p className="texto-suave">Fuente: {API_URL || window.location.origin}/api/autoridades/casos</p>
                </section>
            )}
        </div>
    )
}
