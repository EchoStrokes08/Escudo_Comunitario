import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { collection, onSnapshot, query, orderBy } from 'firebase/firestore'
import { db } from '../services/firebase'
import MapaCalor from '../components/MapaCalor.jsx'
import { nivelRiesgo } from '../utils/riesgo.js'
import { dentroDeBosa } from '../data/bosaPolygon.js'

export default function Dashboard() {
    const [alertas, setAlertas] = useState([])
    const [cargando, setCargando] = useState(true)

    useEffect(() => {
        const q = query(collection(db, 'alertas_bosa'), orderBy('fecha', 'desc'))

        // onSnapshot: la consulta se actualiza en tiempo real
        const unsubscribe = onSnapshot(q, (snapshot) => {
            setAlertas(snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() })))
            setCargando(false)
        }, () => setCargando(false))

        return () => unsubscribe()
    }, [])

    const estadisticas = useMemo(() => {
        // Solo reportes con coordenadas estrictamente dentro de Bosa
        const enBosa = alertas.filter(a =>
            typeof a.lat === 'number' && typeof a.lng === 'number' && dentroDeBosa(a.lat, a.lng)
        )
        const total = enBosa.length
        const alto = enBosa.filter(a => (a.nivel_riesgo || 0) >= 70).length
        const medio = enBosa.filter(a => (a.nivel_riesgo || 0) >= 40 && (a.nivel_riesgo || 0) < 70).length
        const promedio = total
            ? Math.round(enBosa.reduce((suma, a) => suma + (a.nivel_riesgo || 0), 0) / total)
            : 0
        return { total, alto, medio, promedio }
    }, [alertas])

    return (
        <div>
            <section className="encabezado">
                <div>
                    <h2>Panel de Inteligencia Territorial</h2>
                    <p>Monitoreo en tiempo real de reportes de fraude en la localidad de Bosa</p>
                </div>
                <Link to="/reportar" className="boton boton-primario">🚩 Reportar mensaje sospechoso</Link>
            </section>

            <section className="tarjetas-estadisticas">
                <div className="tarjeta-estadistica">
                    <span className="valor">{estadisticas.total}</span>
                    <span className="etiqueta">Reportes totales</span>
                </div>
                <div className="tarjeta-estadistica borde-alto">
                    <span className="valor">{estadisticas.alto}</span>
                    <span className="etiqueta">Riesgo alto</span>
                </div>
                <div className="tarjeta-estadistica borde-medio">
                    <span className="valor">{estadisticas.medio}</span>
                    <span className="etiqueta">Riesgo medio</span>
                </div>
                <div className="tarjeta-estadistica borde-bajo">
                    <span className="valor">{estadisticas.promedio}%</span>
                    <span className="etiqueta">Riesgo promedio</span>
                </div>
            </section>

            <div className="panel-mapa">
                <h3>Mapa de calor · Localidad de Bosa</h3>
                {cargando ? (
                    <p className="texto-suave">Cargando reportes…</p>
                ) : (
                    <MapaCalor reportes={alertas} />
                )}
            </div>

            <section>
                <h3>Últimos reportes</h3>
                <div className="lista-reportes">
                    {alertas.length === 0 ? (
                        <p className="texto-suave">
                            {cargando ? 'Cargando…' : 'Aún no hay reportes. Sé el primero en reportar.'}
                        </p>
                    ) : (
                        alertas.map(alerta => {
                            const { color, etiqueta, clase } = nivelRiesgo(alerta.nivel_riesgo)
                            return (
                                <article key={alerta.id} className={`tarjeta-reporte ${clase}`}>
                                    <div className="reporte-cabecera">
                                        <strong className="certificado">#{(alerta.certificado || '').slice(0, 16)}…</strong>
                                        <span className="chip" style={{ background: color }}>
                                            {etiqueta} · {alerta.nivel_riesgo}%
                                        </span>
                                    </div>

                                    <p className="reporte-mensaje">"{alerta.mensaje_original}"</p>

                                    {alerta.flags?.length > 0 && (
                                        <div className="flags">
                                            {alerta.flags.map(flag => <span key={flag} className="flag">{flag}</span>)}
                                        </div>
                                    )}

                                    {alerta.verificacion?.hallazgos?.length > 0 && (
                                        <p className="hallazgo">
                                            🔍 Cruce de fuentes: {alerta.verificacion.hallazgos[0].detalle}
                                            {' '}({alerta.verificacion.hallazgos[0].valor})
                                        </p>
                                    )}

                                    <div className="reporte-pie">
                                        <span>📍 UPZ {alerta.upz || alerta.barrio || 'Bosa'}</span>
                                        <span>💬 {alerta.canal || 'whatsapp'}</span>
                                        {alerta.adjuntos?.length > 0 && (
                                            <span>📎 {alerta.adjuntos.length} archivo{alerta.adjuntos.length > 1 ? 's' : ''}</span>
                                        )}
                                        <span>
                                            🕒 {new Date(alerta.fecha).toLocaleString('es-CO')}
                                        </span>
                                    </div>
                                </article>
                            )
                        })
                    )}
                </div>
            </section>
        </div>
    )
}
