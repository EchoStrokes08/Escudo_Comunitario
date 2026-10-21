import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Icono from '../components/Icono.jsx'
import { auditarCadena, sellarCertificado, sha256Texto, urlPruebaOts, urlRegistroJson, verificarCertificado } from '../services/api.js'
import { nivelRiesgo, nombreTipo } from '../utils/riesgo.js'

function Auditoria() {
    const [estado, setEstado] = useState(null)
    const [cargando, setCargando] = useState(false)
    const [error, setError] = useState(null)

    const auditar = async () => {
        setCargando(true)
        setError(null)
        try {
            setEstado(await auditarCadena())
        } catch (e) {
            setError(e.message)
        } finally {
            setCargando(false)
        }
    }

    return (
        <div className="panel auditoria">
            <div className="panel-cabecera">
                <h2><Icono nombre="cadena" tamano={18} /> Auditoría de toda la cadena</h2>
            </div>
            <p className="texto-suave">
                Recalcula el SHA-256 de cada reporte y comprueba que cada uno apunte al anterior.
                Si alguien modifica o borra un solo registro, aunque tenga acceso a la base de datos, aparece aquí.
            </p>
            <button type="button" className="boton boton-secundario" onClick={auditar} disabled={cargando}>
                {cargando ? <><span className="spinner" /> Auditando…</> : <><Icono nombre="buscar" /> Auditar ahora</>}
            </button>
            {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}
            {estado && (
                <div className={`resultado-auditoria ${estado.valida ? 'ok' : 'roto'}`}>
                    <strong>
                        <Icono nombre={estado.valida ? 'check' : 'alerta'} tamano={18} />
                        {estado.valida ? 'Cadena íntegra' : 'Se detectaron alteraciones'}
                    </strong>
                    <span>{estado.integros} de {estado.total} bloques íntegros · {estado.anclados} sellados en OpenTimestamps</span>
                    {estado.errores.map((e, i) => (
                        <span key={i} className="error-auditoria">Bloque #{e.altura}: {e.motivo}
                            {e.hash && <> · <Link to={`/verificar/${e.hash}`} className="mono">{e.hash.slice(0, 12)}…</Link></>}
                        </span>
                    ))}
                </div>
            )}
        </div>
    )
}

function CompararMensaje({ hashMensaje }) {
    const [texto, setTexto] = useState('')
    const [coincide, setCoincide] = useState(null)

    const comprobar = async () => setCoincide((await sha256Texto(texto)) === hashMensaje)

    return (
        <div className="bloque-detalle comparar">
            <h3><Icono nombre="mensaje" tamano={16} /> ¿Es este mi mensaje?</h3>
            <p className="texto-suave">
                Pega el mensaje exacto que reportaste. Calculamos su huella <strong>en tu dispositivo</strong> (el
                texto no se envía) y la comparamos con la registrada.
            </p>
            <textarea rows={3} value={texto} onChange={e => { setTexto(e.target.value); setCoincide(null) }}
                placeholder="Pega aquí el mensaje original…" />
            <button type="button" className="boton boton-secundario" onClick={comprobar} disabled={!texto.trim()}>
                <Icono nombre="hash" /> Comparar huella
            </button>
            {coincide !== null && (
                <p className={`aviso ${coincide ? 'aviso-exito' : 'aviso-error'}`}>
                    <Icono nombre={coincide ? 'check' : 'alerta'} tamano={16} />
                    {coincide ? 'Coincide: este es exactamente el mensaje registrado.' : 'No coincide con el mensaje registrado.'}
                </p>
            )}
        </div>
    )
}

export default function Verificar() {
    const { codigo } = useParams()
    const navegar = useNavigate()
    const [entrada, setEntrada] = useState(codigo || '')
    const [datos, setDatos] = useState(null)
    const [error, setError] = useState(null)
    const [cargando, setCargando] = useState(false)

    useEffect(() => {
        if (!codigo) return
        setEntrada(codigo)
        setCargando(true)
        setError(null)
        setDatos(null)
        verificarCertificado(codigo)
            .then(async d => {
                setDatos(d)
                // Si el sello en Bitcoin quedó pendiente, se completa ahora y se recarga
                if (d.integro && !d.anclaje.descargable) {
                    await sellarCertificado(d.certificado).catch(() => null)
                    setDatos(await verificarCertificado(d.certificado).catch(() => d))
                }
            })
            .catch(e => setError(e.message))
            .finally(() => setCargando(false))
    }, [codigo])

    const buscar = (e) => {
        e.preventDefault()
        const limpio = entrada.trim().toLowerCase().replace(/[^0-9a-f]/g, '')
        if (limpio) navegar(`/verificar/${limpio}`)
    }

    const b = datos?.bloque
    const nivel = b ? nivelRiesgo(b.analisis.nivel_riesgo) : null

    return (
        <div className="pagina-verificar">
            <section className="hero hero-compacto">
                <div className="hero-texto">
                    <span className="eyebrow"><Icono nombre="candado" tamano={14} /> Registro público e inmutable</span>
                    <h1>Verificar un certificado</h1>
                    <p>
                        Cualquier persona (una víctima, la Policía, un juez) puede comprobar que un reporte existe,
                        cuándo se hizo y que nadie lo ha alterado desde entonces.
                    </p>
                </div>
            </section>

            <form className="buscador-certificado" onSubmit={buscar}>
                <Icono nombre="hash" tamano={18} />
                <input value={entrada} onChange={e => setEntrada(e.target.value)} spellCheck={false}
                    placeholder="Pega el código del certificado (completo o los primeros 16 caracteres)" aria-label="Código del certificado" />
                <button className="boton boton-primario" type="submit">Verificar</button>
            </form>

            {cargando && <div className="cargando-pagina"><span className="spinner" /></div>}
            {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}

            {datos && (
                <section className={`verificacion ${datos.integro ? 'integro' : 'alterado'}`}>
                    <div className="verificacion-sello">
                        <span className="sello-icono"><Icono nombre={datos.integro ? 'check' : 'alerta'} tamano={34} grosor={2.4} /></span>
                        <div>
                            <h2>{datos.integro ? 'Certificado íntegro' : 'Certificado alterado'}</h2>
                            <p>{datos.integro
                                ? 'El contenido registrado coincide exactamente con su huella SHA-256.'
                                : 'El contenido guardado ya no coincide con su huella: alguien lo modificó después de registrarlo.'}</p>
                        </div>
                    </div>

                    <div className="veredicto-detalles">
                        <div className="bloque-detalle">
                            <h3><Icono nombre="archivo" tamano={16} /> Bloque #{b.altura}</h3>
                            <dl className="datos-bloque">
                                <dt>Fecha</dt><dd>{new Date(b.fecha).toLocaleString('es-CO')}</dd>
                                <dt>Canal</dt><dd>{b.canal}</dd>
                                <dt>Riesgo</dt><dd className={`texto-${nivel.id}`}>{b.analisis.nivel_riesgo}% · {nivel.etiqueta}</dd>
                                <dt>Confianza</dt><dd>{b.analisis.confianza}%</dd>
                                <dt>Tipo</dt><dd>{nombreTipo(b.analisis.tipo_fraude)}</dd>
                                {datos.reporte?.upz && <><dt>UPZ</dt><dd>{datos.reporte.upz}</dd></>}
                                <dt>Huella del mensaje</dt><dd className="mono">{b.hash_mensaje.slice(0, 16)}…</dd>
                                <dt>Archivos</dt><dd>{b.adjuntos.length ? `${b.adjuntos.length} (huellas SHA-256 registradas)` : 'Ninguno'}</dd>
                            </dl>
                            {datos.reporte?.mensaje_anonimizado && <p className="reporte-mensaje">“{datos.reporte.mensaje_anonimizado}”</p>}
                        </div>

                        <div className="bloque-detalle">
                            <h3><Icono nombre="cadena" tamano={16} /> Encadenamiento</h3>
                            <ul className="eslabones">
                                <li className={datos.enlaces.anterior_valido ? 'ok' : 'roto'}>
                                    <Icono nombre={datos.enlaces.anterior_valido ? 'check' : 'alerta'} tamano={14} />
                                    <span>Anterior {b.altura === 0
                                        ? '(bloque génesis)'
                                        : <Link to={`/verificar/${datos.enlaces.anterior}`} className="mono">{datos.enlaces.anterior.slice(0, 12)}…</Link>}</span>
                                </li>
                                <li className="actual"><Icono nombre="candado" tamano={14} /><span className="mono">{datos.certificado.slice(0, 12)}… (este)</span></li>
                                <li className={datos.enlaces.siguiente ? (datos.enlaces.siguiente_apunta_aqui ? 'ok' : 'roto') : 'pendiente'}>
                                    <Icono nombre={datos.enlaces.siguiente ? 'check' : 'reloj'} tamano={14} />
                                    <span>Siguiente {datos.enlaces.siguiente
                                        ? <Link to={`/verificar/${datos.enlaces.siguiente}`} className="mono">{datos.enlaces.siguiente.slice(0, 12)}…</Link>
                                        : '(aún no hay reportes posteriores)'}</span>
                                </li>
                            </ul>

                            <h3 className="subtitulo-bloque"><Icono nombre="candado" tamano={16} /> Sello de tiempo en Bitcoin</h3>
                            {datos.anclaje.descargable ? (
                                <>
                                    <p className="texto-suave">
                                        Anclado vía OpenTimestamps ({datos.anclaje.calendario?.replace('https://', '')}).
                                        Descarga los dos archivos y súbelos a <a href="https://opentimestamps.org" target="_blank" rel="noreferrer">opentimestamps.org</a> para
                                        comprobarlo sin confiar en nosotros.
                                    </p>
                                    <div className="plan-enlaces">
                                        <a className="boton boton-secundario" href={urlRegistroJson(datos.certificado)}><Icono nombre="descargar" /> registro.json</a>
                                        <a className="boton boton-secundario" href={urlPruebaOts(datos.certificado)}><Icono nombre="descargar" /> prueba .ots</a>
                                    </div>
                                </>
                            ) : <p className="texto-suave"><span className="spinner spinner-pequeno" /> Sellando en Bitcoin vía OpenTimestamps…</p>}
                        </div>

                        <CompararMensaje hashMensaje={b.hash_mensaje} />
                    </div>

                    <div className="veredicto-acciones">
                        <Link to={`/certificado/${datos.certificado}`} className="boton boton-primario"><Icono nombre="imprimir" /> Ver certificado imprimible</Link>
                    </div>
                </section>
            )}

            <Auditoria />
        </div>
    )
}
