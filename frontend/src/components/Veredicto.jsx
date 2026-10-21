import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Icono from './Icono.jsx'
import CodigoQR from './CodigoQR.jsx'
import { nivelRiesgo } from '../utils/riesgo.js'
import { useContador } from '../hooks/animacion.js'

const TITULARES = {
    alto: 'Muy probablemente es un fraude',
    medio: 'Ten cuidado con este mensaje',
    bajo: 'No vemos señales graves',
}

const ESTADO_FUENTE = {
    consultada: { clase: 'fuente-ok', texto: 'Consultada' },
    'no configurada': { clase: 'fuente-off', texto: 'No configurada' },
    error: { clase: 'fuente-error', texto: 'Sin respuesta' },
}

/** Anillo animado con el porcentaje de riesgo. */
function MedidorRiesgo({ valor, nivel }) {
    const radio = 52
    const circunferencia = 2 * Math.PI * radio
    const [progreso, setProgreso] = useState(0)
    const numero = useContador(valor, 1200)

    useEffect(() => {
        const marco = requestAnimationFrame(() => setProgreso(valor))
        return () => cancelAnimationFrame(marco)
    }, [valor])

    return (
        <div className={`medidor ${nivel.clase}`}>
            <svg viewBox="0 0 120 120" aria-hidden="true">
                <circle className="medidor-pista" cx="60" cy="60" r={radio} />
                <circle
                    className="medidor-arco"
                    cx="60" cy="60" r={radio}
                    strokeDasharray={circunferencia}
                    strokeDashoffset={circunferencia * (1 - progreso / 100)}
                />
            </svg>
            <div className="medidor-centro">
                <span className="medidor-valor">{numero}<small>%</small></span>
                <span className="medidor-etiqueta">Riesgo {nivel.etiqueta.toLowerCase()}</span>
            </div>
        </div>
    )
}

/** Lee el veredicto en voz alta (síntesis de voz del navegador, sin servicios externos). */
function BotonEscuchar({ texto }) {
    const [hablando, setHablando] = useState(false)
    const disponible = typeof window !== 'undefined' && 'speechSynthesis' in window

    useEffect(() => () => disponible && window.speechSynthesis.cancel(), [disponible])
    if (!disponible) return null

    const alternar = () => {
        const voz = window.speechSynthesis
        if (hablando) {
            voz.cancel()
            setHablando(false)
            return
        }
        const frase = new SpeechSynthesisUtterance(texto)
        frase.lang = 'es-CO'
        frase.rate = 0.95
        const espanol = voz.getVoices().find(v => v.lang === 'es-CO') || voz.getVoices().find(v => v.lang.startsWith('es'))
        if (espanol) frase.voice = espanol
        frase.onend = () => setHablando(false)
        frase.onerror = () => setHablando(false)
        voz.cancel()
        voz.speak(frase)
        setHablando(true)
    }

    return (
        <button type="button" className={`boton boton-secundario boton-escuchar ${hablando ? 'activo' : ''}`} onClick={alternar}>
            <Icono nombre={hablando ? 'detener' : 'altavoz'} tamano={16} /> {hablando ? 'Detener' : 'Escuchar resultado'}
        </button>
    )
}

export default function Veredicto({ resultado: r, onNuevo }) {
    const [copiado, setCopiado] = useState(false)
    const nivel = nivelRiesgo(r.nivel_riesgo)
    const hallazgos = r.verificacion?.hallazgos || []
    const fuentes = r.verificacion?.fuentes || []
    const plan = r.plan_accion || []
    const esAudio = (r.adjuntos || []).some(a => a.mime?.startsWith('audio/'))
    const anclado = r.anclaje?.estado === 'pendiente_bitcoin'

    const textoVoz = [
        TITULARES[nivel.id] + '.',
        `Riesgo ${r.nivel_riesgo} por ciento, confianza ${r.nivel_confianza}.`,
        r.resumen,
        plan.length ? 'Qué hacer ahora:' : '',
        ...plan.slice(0, 3).map((p, i) => `${i + 1}. ${p.titulo}. ${p.detalle}`),
    ].join(' ')

    const copiar = async () => {
        try {
            await navigator.clipboard.writeText(r.certificado)
            setCopiado(true)
            setTimeout(() => setCopiado(false), 2000)
        } catch { /* el código sigue visible para copiarlo a mano */ }
    }

    return (
        <section className={`veredicto ${nivel.clase}`}>
            <div className="veredicto-cabecera">
                <MedidorRiesgo valor={r.nivel_riesgo} nivel={nivel} />
                <div className="veredicto-texto">
                    <span className="eyebrow">Veredicto del análisis</span>
                    <h2>{TITULARES[nivel.id]}</h2>
                    <div className="veredicto-chips">
                        {r.tipo_fraude?.id !== 'legitimo' && <span className={`chip chip-${nivel.id}`}>{r.tipo_fraude?.nombre}</span>}
                        <span className={`chip chip-confianza confianza-${r.nivel_confianza}`}>
                            <Icono nombre="escudo" tamano={13} /> Confianza {r.nivel_confianza} · {r.confianza}%
                        </span>
                        {r.entidad_suplantada && <span className="chip chip-neutro">Suplanta a: {r.entidad_suplantada}</span>}
                    </div>
                    <p>{r.resumen}</p>
                    {r.flags?.length > 0 && (
                        <div className="flags">
                            {r.flags.map(flag => <span key={flag} className="flag">{flag}</span>)}
                        </div>
                    )}
                    <BotonEscuchar texto={textoVoz} />
                </div>
            </div>

            {r.motor && r.motor !== 'llm' && (
                <p className="aviso aviso-medio">
                    <Icono nombre="alerta" tamano={16} />
                    <span>La IA no respondió a tiempo: este veredicto viene del análisis local de respaldo, con confianza limitada.</span>
                </p>
            )}

            {/* Qué hacer ahora */}
            {plan.length > 0 && (
                <div className="plan-accion">
                    <h3><Icono nombre="bandera" tamano={16} /> Qué hacer ahora</h3>
                    <ol>
                        {plan.map((paso, i) => (
                            <li key={paso.titulo} className={paso.urgente ? 'urgente' : ''}>
                                <span className="plan-numero">{i + 1}</span>
                                <div>
                                    <strong>{paso.titulo}</strong>
                                    <p>{paso.detalle}</p>
                                    <div className="plan-enlaces">
                                        {paso.telefono && <a href={`tel:${paso.telefono}`} className="boton-texto"><Icono nombre="llamar" tamano={14} /> Llamar al {paso.telefono}</a>}
                                        {paso.enlace && <a href={paso.enlace} target="_blank" rel="noreferrer" className="boton-texto"><Icono nombre="externo" tamano={14} /> Abrir sitio oficial</a>}
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ol>
                </div>
            )}

            <div className="veredicto-detalles">
                {/* Verificación en fuentes abiertas */}
                <div className="bloque-detalle">
                    <h3><Icono nombre="buscar" tamano={16} /> Verificación en tiempo real</h3>
                    {hallazgos.length === 0 && <p className="texto-suave hallazgo-vacio">No encontramos el enlace, la cuenta ni el número en las fuentes consultadas.</p>}
                    {hallazgos.map((h, i) => (
                        <div key={i} className="hallazgo-item">
                            <strong className="mono">{h.valor}</strong>
                            <span>{h.detalle}</span>
                            <small>{h.fuente}{h.simulada && <span className="etiqueta-demo">demo</span>}</small>
                        </div>
                    ))}
                    <ul className="lista-fuentes">
                        {fuentes.map(f => {
                            const e = ESTADO_FUENTE[f.estado] || ESTADO_FUENTE.error
                            return <li key={f.nombre}><i className={`punto-fuente ${e.clase}`} />{f.nombre}<span>{e.texto}</span></li>
                        })}
                    </ul>
                </div>

                {/* Por qué esta confianza */}
                <div className="bloque-detalle">
                    <h3><Icono nombre="pulso" tamano={16} /> Por qué confiamos {r.confianza}%</h3>
                    <ul className="factores">
                        {(r.factores_confianza || []).map((f, i) => (
                            <li key={i} className={`factor factor-${f.tipo}`}>
                                <Icono nombre={f.tipo === 'sube' ? 'check' : f.tipo === 'baja' || f.tipo === 'alerta' ? 'alerta' : 'chispa'} tamano={14} />
                                {f.texto}
                            </li>
                        ))}
                    </ul>
                    {r.comunidad?.length > 0 && (
                        <p className="aviso aviso-error comunidad-aviso">
                            <Icono nombre="usuarios" tamano={16} />
                            <span><strong>Otros vecinos ya lo reportaron:</strong> {r.comunidad.map(c => `${c.valor} (${c.veces} ${c.veces === 1 ? 'vez' : 'veces'})`).join(', ')}</span>
                        </p>
                    )}
                </div>

                {(r.texto_detectado || r.adjuntos_analizados > 0) && (
                    <div className="bloque-detalle">
                        <h3><Icono nombre={esAudio ? 'microfono' : 'clip'} tamano={16} /> {esAudio ? 'Lo que entendimos de tu audio' : 'Lo que leímos en tus archivos'}</h3>
                        {r.texto_detectado && <p className="texto-detectado">“{r.texto_detectado}”</p>}
                        {(r.adjuntos || []).map((a, i) => (
                            <div key={i} className="hallazgo-item">
                                <strong>{a.mime?.startsWith('audio/') ? 'Nota de voz' : a.nombre}</strong>
                                <small className="mono">SHA-256 {a.sha256.slice(0, 32)}…</small>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Certificado */}
            <div className="certificado-caja certificado-v2">
                <div className="certificado-info">
                    <div className="certificado-cabecera">
                        <h3><Icono nombre="candado" tamano={16} /> Certificado de reporte · bloque #{r.altura}</h3>
                        <button type="button" className={`boton-texto ${copiado ? 'copiado' : ''}`} onClick={copiar}>
                            <Icono nombre={copiado ? 'check' : 'copiar'} tamano={15} /> {copiado ? 'Copiado' : 'Copiar'}
                        </button>
                    </div>
                    <code>{r.certificado}</code>
                    <ul className="sellos">
                        <li><Icono nombre="cadena" tamano={14} /> Encadenado al bloque anterior <span className="mono">{r.prev?.slice(0, 10)}…</span></li>
                        <li className={anclado ? '' : 'pendiente'}>
                            <Icono nombre="candado" tamano={14} />
                            {anclado ? 'Sellado en Bitcoin vía OpenTimestamps (confirmación en ~horas)' : 'Sello en Bitcoin pendiente: se reintentará'}
                        </li>
                        <li><Icono nombre="pin" tamano={14} /> UPZ {r.upz} · {new Date(r.fecha).toLocaleString('es-CO')}</li>
                    </ul>
                    <div className="veredicto-acciones">
                        <Link to={`/certificado/${r.certificado}`} className="boton boton-primario"><Icono nombre="imprimir" /> Ver e imprimir certificado</Link>
                        <Link to={`/verificar/${r.certificado}`} className="boton boton-secundario"><Icono nombre="escudo" /> Verificar integridad</Link>
                    </div>
                </div>
                <div className="certificado-qr">
                    <CodigoQR texto={r.url_verificacion || `${window.location.origin}/verificar/${r.certificado}`} />
                    <small>Escanéalo para verificar</small>
                </div>
            </div>

            <div className="veredicto-acciones">
                <Link to="/" className="boton boton-secundario"><Icono nombre="mapa" /> Ver en el panel territorial</Link>
                <button type="button" className="boton boton-secundario" onClick={onNuevo}><Icono nombre="recargar" /> Hacer otro reporte</button>
            </div>
        </section>
    )
}
