import { useState } from 'react'
import { BARRIOS_BOSA } from '../data/barrios.js'
import { nivelRiesgo } from '../utils/riesgo.js'

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export default function Reportar() {
    const [mensaje, setMensaje] = useState('')
    const [barrio, setBarrio] = useState('')
    const [cargando, setCargando] = useState(false)
    const [error, setError] = useState(null)
    const [resultado, setResultado] = useState(null)

    const enviar = async (e) => {
        e.preventDefault()
        if (mensaje.trim().length < 10) {
            setError('Pega el mensaje completo (mínimo 10 caracteres).')
            return
        }

        setCargando(true)
        setError(null)
        setResultado(null)

        try {
            const respuesta = await fetch(`${API_URL}/api/reporte-web`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mensaje: mensaje.trim(), barrio: barrio || null }),
            })

            if (!respuesta.ok) throw new Error('El servicio no respondió. Intenta de nuevo.')

            setResultado(await respuesta.json())
        } catch (err) {
            setError(err.message || 'No se pudo enviar el reporte. Verifica tu conexión.')
        } finally {
            setCargando(false)
        }
    }

    const nivel = resultado ? nivelRiesgo(resultado.nivel_riesgo) : null

    return (
        <div className="pagina-reporte">
            <section className="encabezado">
                <div>
                    <h2>Canal de denuncia ciudadana</h2>
                    <p>
                        Pega el mensaje sospechoso que recibiste. Nuestra IA lo analiza,
                        lo cruza con fuentes abiertas y te entrega un certificado trazable.
                    </p>
                </div>
            </section>

            <form className="formulario" onSubmit={enviar}>
                <label htmlFor="mensaje">
                    Mensaje sospechoso <span className="obligatorio">(obligatorio)</span>
                </label>
                <textarea
                    id="mensaje"
                    rows={6}
                    placeholder="Ej: Felicidades, ganaste un premio de $5.000.000 en la lotería Bogotá. Ingresa aquí www.premios-bogota.top y consigna el impuesto en Nequi 3001234567 antes de las 6pm…"
                    value={mensaje}
                    onChange={e => setMensaje(e.target.value)}
                />

                <label htmlFor="barrio">Barrio de la localidad de Bosa (opcional)</label>
                <select id="barrio" value={barrio} onChange={e => setBarrio(e.target.value)}>
                    <option value="">Selecciona tu barrio…</option>
                    {BARRIOS_BOSA.map(b => (
                        <option key={b.nombre} value={b.nombre}>{b.nombre}</option>
                    ))}
                </select>

                <button className="boton boton-primario" type="submit" disabled={cargando}>
                    {cargando ? '🔍 Analizando…' : 'Analizar y reportar'}
                </button>

                {error && <p className="error">⚠️ {error}</p>}
            </form>

            {resultado && (
                <section className={`veredicto ${nivel.clase}`}>
                    <div className="veredicto-cabecera">
                        <div>
                            <h3>Veredicto del análisis</h3>
                            <p className="texto-suave">{resultado.resumen}</p>
                        </div>
                        <div className="semaforo" style={{ background: nivel.color }}>
                            <span className="semaforo-valor">{resultado.nivel_riesgo}%</span>
                            <span className="semaforo-etiqueta">Riesgo {nivel.etiqueta}</span>
                        </div>
                    </div>

                    {resultado.flags?.length > 0 && (
                        <div className="flags">
                            {resultado.flags.map(flag => <span key={flag} className="flag">{flag}</span>)}
                        </div>
                    )}

                    {resultado.verificacion?.hallazgos?.length > 0 && (
                        <div className="hallazgos">
                            <h4>🔍 Coincidencias en fuentes abiertas</h4>
                            {resultado.verificacion.hallazgos.map((h, i) => (
                                <p key={i}>
                                    <strong>{h.valor}</strong> — {h.detalle}
                                    <br /><small>{h.fuente}</small>
                                </p>
                            ))}
                        </div>
                    )}

                    <div className="certificado-caja">
                        <h4>🛡️ Certificado de reporte (SHA-256)</h4>
                        <code>{resultado.certificado}</code>
                        <p className="texto-suave">
                            Registrado en Bosa · {resultado.barrio} ·{' '}
                            {new Date(resultado.fecha).toLocaleString('es-CO')}
                        </p>
                        <p className="texto-suave">
                            Tu reporte ya aparece en el
                            <a href="/"> panel de inteligencia territorial</a> y en el
                            mapa de calor en tiempo real.
                        </p>
                    </div>
                </section>
            )}
        </div>
    )
}
