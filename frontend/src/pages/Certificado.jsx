import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Icono from '../components/Icono.jsx'
import CodigoQR from '../components/CodigoQR.jsx'
import { sellarCertificado, verificarCertificado } from '../services/api.js'
import { nivelRiesgo, nombreTipo } from '../utils/riesgo.js'
import { selloIncompleto, textoSello } from '../utils/sello.js'
import LineaTiempo from '../components/LineaTiempo.jsx'

/** Certificado de reporte imprimible (Ctrl+P → Guardar como PDF) con QR de verificación. */
export default function Certificado() {
    const { codigo } = useParams()
    const [datos, setDatos] = useState(null)
    const [error, setError] = useState(null)

    useEffect(() => {
        verificarCertificado(codigo)
            .then(async d => {
                // Un código de seguimiento lleva al certificado del reporte
                if (d.tipo === 'seguimiento' && d.caso) d = await verificarCertificado(d.caso)
                setDatos(d)
                if (d.integro && selloIncompleto(d.anclaje)) {
                    await sellarCertificado(d.certificado).catch(() => null)
                    setDatos(await verificarCertificado(d.certificado).catch(() => d))
                }
            })
            .catch(e => setError(e.message))
    }, [codigo])

    if (error) return <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>
    if (!datos) return <div className="cargando-pagina"><span className="spinner" /></div>

    const b = datos.bloque
    const nivel = nivelRiesgo(b.analisis.nivel_riesgo)
    const urlVerificacion = `${window.location.origin}/verificar/${datos.certificado}`

    return (
        <div className="pagina-certificado">
            <div className="acciones-certificado no-imprimir">
                <Link to={`/verificar/${datos.certificado}`} className="boton boton-secundario"><Icono nombre="escudo" /> Verificar en línea</Link>
                <button type="button" className="boton boton-primario" onClick={() => window.print()}><Icono nombre="imprimir" /> Imprimir o guardar PDF</button>
            </div>

            <article className="documento-certificado">
                <header>
                    <div className="doc-marca">
                        <Icono nombre="escudo" tamano={34} grosor={2} />
                        <div>
                            <strong>Escudo Comunitario</strong>
                            <span>Prevención de fraude digital · Localidad 07 Bosa, Bogotá D.C.</span>
                        </div>
                    </div>
                    <span className={`doc-estado ${datos.integro ? 'ok' : 'roto'}`}>
                        {datos.integro ? '✓ Íntegro' : '✗ Alterado'}
                    </span>
                </header>

                <h1>Certificado de reporte de fraude digital</h1>
                <p className="doc-intro">
                    Este documento certifica que el siguiente reporte fue registrado en el registro público e inmutable
                    de Escudo Comunitario. Su contenido está protegido por una huella SHA-256 encadenada al registro
                    anterior y sellada en la red Bitcoin mediante OpenTimestamps.
                </p>

                <dl className="doc-datos">
                    <dt>Fecha y hora del registro</dt><dd>{new Date(b.fecha).toLocaleString('es-CO', { dateStyle: 'long', timeStyle: 'medium' })}</dd>
                    <dt>Canal</dt><dd>{{ whatsapp: 'WhatsApp', telegram: 'Telegram', chat: 'Chat web' }[b.canal] || 'Formulario web'}</dd>
                    {datos.estado_caso && <><dt>Estado del caso</dt><dd><strong>{datos.estado_caso.etiqueta}</strong>
                        {datos.estado_caso.estado !== 'registrado' && <> · {datos.estado_caso.actor} · {new Date(datos.estado_caso.fecha).toLocaleDateString('es-CO')}</>}</dd></>}
                    <dt>Tipo de fraude</dt><dd>{nombreTipo(b.analisis.tipo_fraude)}</dd>
                    <dt>Nivel de riesgo</dt><dd>{b.analisis.nivel_riesgo}% ({nivel.etiqueta}) · confianza {b.analisis.confianza}%</dd>
                    {datos.reporte?.upz && <><dt>UPZ</dt><dd>{datos.reporte.upz}</dd></>}
                    <dt>Señales detectadas</dt><dd>{b.analisis.flags.join(' · ') || '—'}</dd>
                    <dt>Posición en la cadena</dt><dd>Bloque #{b.altura}</dd>
                    <dt>Huella del mensaje</dt><dd className="mono">{b.hash_mensaje}</dd>
                    {b.adjuntos.length > 0 && <><dt>Huellas de archivos</dt><dd className="mono">{b.adjuntos.map(h => <span key={h}>{h}<br /></span>)}</dd></>}
                </dl>

                {datos.seguimiento?.length > 1 && (
                    <div className="doc-seguimiento">
                        <span>Seguimiento del caso (cada paso es un bloque encadenado)</span>
                        <LineaTiempo eventos={datos.seguimiento} compacta />
                    </div>
                )}

                <div className="doc-hash">
                    <div>
                        <span>Código del certificado (SHA-256)</span>
                        <code>{datos.certificado}</code>
                        <span>Bloque anterior</span>
                        <code className="tenue">{datos.enlaces.anterior}</code>
                        <span>Sello de tiempo</span>
                        <p>{textoSello(datos.anclaje)}</p>
                    </div>
                    <div className="doc-qr">
                        <CodigoQR texto={urlVerificacion} tamano={132} />
                        <small>Escanee para verificar</small>
                    </div>
                </div>

                <footer>
                    <p>
                        <strong>Cómo verificarlo:</strong> escanee el código QR o ingrese a {window.location.host}/verificar
                        con el código del certificado. Cualquier modificación del reporte cambia su huella e invalida el certificado.
                        El texto completo del mensaje no se publica; la persona denunciante puede comprobar que corresponde
                        a su mensaje comparando la huella.
                    </p>
                    <p className="doc-legal">
                        Presente este certificado junto con su denuncia en el CAI Virtual de la Policía Nacional
                        (caivirtual.policia.gov.co) o en la Fiscalía General de la Nación (línea 122).
                    </p>
                </footer>
            </article>
        </div>
    )
}
