import { Link } from 'react-router-dom'
import Icono from './Icono.jsx'
import { ESTADOS_CASO, ORDEN_ESTADOS } from '../utils/estados.js'

/**
 * Línea de tiempo del caso: cada paso es un bloque encadenado de la cadena con su
 * propia comprobación de integridad. Los estados aún no alcanzados se muestran tenues.
 */
export default function LineaTiempo({ eventos, compacta = false }) {
    if (!eventos?.length) return null
    const actual = eventos[eventos.length - 1].estado
    const alcanzados = new Set(eventos.map(e => e.estado))
    const pendientes = actual === 'cerrado' ? [] : ORDEN_ESTADOS.slice(ORDEN_ESTADOS.indexOf(actual) + 1)
        .filter(e => !alcanzados.has(e))

    return (
        <ol className={`linea-tiempo ${compacta ? 'compacta' : ''}`}>
            {eventos.map((e, i) => (
                <li key={e.certificado} className={`paso-caso hecho ${i === eventos.length - 1 ? 'actual' : ''} ${e.integro ? '' : 'alterado'}`}>
                    <span className="paso-caso-icono"><Icono nombre={e.integro ? (ESTADOS_CASO[e.estado]?.icono || 'check') : 'alerta'} tamano={14} grosor={2.2} /></span>
                    <div className="paso-caso-texto">
                        <strong>{e.etiqueta}{!e.integro && <span className="texto-alto"> · alterado</span>}</strong>
                        <small>
                            {new Date(e.fecha).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })}
                            {e.estado !== 'registrado' && e.actor && <> · {e.actor}</>}
                        </small>
                        {e.nota && <p>“{e.nota}”</p>}
                        {!compacta && (
                            <Link to={`/verificar/${e.certificado}`} className="mono paso-caso-bloque">
                                <Icono nombre="cadena" tamano={11} /> bloque #{e.altura} · {e.certificado.slice(0, 10)}…
                            </Link>
                        )}
                    </div>
                </li>
            ))}
            {!compacta && pendientes.map(e => (
                <li key={e} className="paso-caso pendiente">
                    <span className="paso-caso-icono"><Icono nombre={ESTADOS_CASO[e].icono} tamano={14} /></span>
                    <div className="paso-caso-texto"><strong>{ESTADOS_CASO[e].etiqueta}</strong></div>
                </li>
            ))}
        </ol>
    )
}
