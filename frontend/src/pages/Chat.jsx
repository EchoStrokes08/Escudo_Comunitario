import { Fragment, useEffect, useRef, useState } from 'react'
import Icono from '../components/Icono.jsx'
import GrabadorVoz from '../components/GrabadorVoz.jsx'
import { API_URL, pedir, sellarCertificado } from '../services/api.js'
import { TELEGRAM_BOT, URL_TELEGRAM, URL_WHATSAPP, WHATSAPP_VISIBLE } from '../utils/canales.js'

const CLAVE_SESION = 'escudo-chat-sesion'
const MAX_PESO = 2 * 1024 * 1024
const TIPOS_ARCHIVO = ['image/png', 'image/jpeg', 'image/webp', 'application/pdf']

function obtenerSesion() {
    try {
        let sesion = localStorage.getItem(CLAVE_SESION)
        if (!sesion) {
            sesion = crypto.randomUUID()
            localStorage.setItem(CLAVE_SESION, sesion)
        }
        return sesion
    } catch {
        return crypto.randomUUID()
    }
}

const hora = () => new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })

/** Formato de WhatsApp: *negrita*, saltos de línea y enlaces. */
function TextoWhatsApp({ texto }) {
    return texto.split('\n').map((linea, i) => (
        <Fragment key={i}>
            {i > 0 && <br />}
            {linea.split(/(\*[^*\n]+\*|https?:\/\/\S+)/g).map((parte, j) => {
                if (/^\*[^*]+\*$/.test(parte)) return <strong key={j}>{parte.slice(1, -1)}</strong>
                if (/^https?:\/\//.test(parte)) return <a key={j} href={parte} target="_blank" rel="noreferrer">{parte.replace(/^https?:\/\//, '')}</a>
                return parte
            })}
        </Fragment>
    ))
}

function leerBase64(archivo) {
    return new Promise((resolve, reject) => {
        const lector = new FileReader()
        lector.onload = () => resolve(String(lector.result).split(',')[1])
        lector.onerror = reject
        lector.readAsDataURL(archivo)
    })
}

/**
 * Simulador del bot de WhatsApp: misma conversación y misma lógica que el canal
 * de Twilio (POST /api/whatsapp/simulador). Útil para la demo y para quien no
 * tenga WhatsApp a mano.
 */
export default function Chat() {
    const [sesion] = useState(obtenerSesion)
    const [mensajes, setMensajes] = useState([])
    const [opciones, setOpciones] = useState([])
    const [texto, setTexto] = useState('')
    const [escribiendo, setEscribiendo] = useState(false)
    const [error, setError] = useState(null)
    const fin = useRef(null)
    const inputArchivo = useRef(null)
    const iniciado = useRef(false)

    // Desplaza solo la conversación (no la página) hasta el último mensaje
    useEffect(() => {
        const caja = fin.current?.parentElement
        if (caja) caja.scrollTo({ top: caja.scrollHeight, behavior: 'smooth' })
    }, [mensajes, escribiendo])

    const enviar = async ({ visible, cuerpo }) => {
        setError(null)
        if (visible) setMensajes(m => [...m, { de: 'yo', hora: hora(), ...visible }])
        setOpciones([])
        setEscribiendo(true)
        try {
            const r = await pedir('/api/whatsapp/simulador', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sesion, ...cuerpo }),
            })
            // Los mensajes del bot llegan uno tras otro, como en WhatsApp
            for (const [i, m] of r.mensajes.entries()) {
                if (i > 0) await new Promise(res => setTimeout(res, 700))
                setMensajes(prev => [...prev, { de: 'bot', texto: m, hora: hora() }])
            }
            // Quien mandó una nota de voz (o escribió "escuchar") recibe también el veredicto hablado
            if (r.audio) setMensajes(prev => [...prev, { de: 'bot', audio: `${API_URL}${r.audio}`, hora: hora() }])
            setOpciones(r.opciones || [])
            // Sello en Bitcoin en segundo plano: la respuesta ya se mostró
            if (r.certificado) sellarCertificado(r.certificado).catch(() => {})
        } catch (e) {
            setError(e.message)
        } finally {
            setEscribiendo(false)
        }
    }

    useEffect(() => {
        if (iniciado.current) return
        iniciado.current = true
        enviar({ cuerpo: { texto: 'hola' } })
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

    const enviarTexto = (e) => {
        e.preventDefault()
        const limpio = texto.trim()
        if (!limpio || escribiendo) return
        setTexto('')
        enviar({ visible: { texto: limpio }, cuerpo: { texto: limpio } })
    }

    const enviarArchivo = async (archivo) => {
        if (!archivo) return
        if (!TIPOS_ARCHIVO.includes(archivo.type) || archivo.size > MAX_PESO) {
            setError('Envía una captura (PNG, JPG, WEBP) o un PDF de máximo 2 MB.')
            return
        }
        const base64 = await leerBase64(archivo)
        const imagen = archivo.type.startsWith('image/') ? `data:${archivo.type};base64,${base64}` : null
        const leyenda = texto.trim()
        setTexto('')
        enviar({
            visible: { imagen, archivo: imagen ? null : archivo.name, texto: leyenda },
            cuerpo: { texto: leyenda, adjuntos: [{ nombre: archivo.name, mime: archivo.type, base64 }] },
        })
    }

    const enviarVoz = (nota) => enviar({
        visible: { audio: nota.url },
        cuerpo: { adjuntos: [{ nombre: nota.nombre, mime: nota.mime, base64: nota.base64 }] },
    })

    const compartirUbicacion = () => {
        if (!navigator.geolocation) {
            setError('Tu navegador no permite compartir la ubicación. Elige tu UPZ.')
            return
        }
        navigator.geolocation.getCurrentPosition(
            ({ coords }) => enviar({
                visible: { texto: '📍 Ubicación compartida' },
                cuerpo: { lat: coords.latitude, lng: coords.longitude },
            }),
            () => setError('No pudimos obtener tu ubicación. Elige tu UPZ en las opciones.'),
            { enableHighAccuracy: true, timeout: 10000 },
        )
    }

    return (
        <div className="pagina-chat">
            <section className="hero hero-compacto">
                <div className="hero-texto">
                    <span className="eyebrow"><Icono nombre="mensaje" tamano={14} /> Simulador del canal de WhatsApp</span>
                    <h1>Habla con el Escudo</h1>
                    <p>
                        El mismo asistente que atiende por WhatsApp. Escríbele, mándale una captura o
                        <strong> cuéntale lo que pasó con una nota de voz</strong>.
                    </p>
                    <div className="enlaces-canales">
                        <a href={URL_WHATSAPP} target="_blank" rel="noreferrer" className="boton boton-whatsapp">
                            <Icono nombre="mensaje" tamano={16} /> WhatsApp {WHATSAPP_VISIBLE}
                        </a>
                        <a href={URL_TELEGRAM} target="_blank" rel="noreferrer" className="boton boton-secundario">
                            <Icono nombre="mensaje" tamano={16} /> Telegram @{TELEGRAM_BOT}
                        </a>
                    </div>
                </div>
            </section>

            <div className="telefono">
                <header className="chat-cabecera">
                    <span className="chat-avatar"><Icono nombre="escudo" tamano={20} grosor={2} /></span>
                    <div>
                        <strong>Escudo Comunitario Bosa</strong>
                        <small>{escribiendo ? 'escribiendo…' : 'en línea'}</small>
                    </div>
                </header>

                <div className="chat-mensajes" aria-live="polite">
                    <p className="chat-aviso"><Icono nombre="candado" tamano={12} /> Anónimo: tu reporte se guarda sin tu número ni tus datos.</p>
                    {mensajes.map((m, i) => (
                        <div key={i} className={`burbuja ${m.de === 'yo' ? 'mia' : 'bot'}`}>
                            {m.imagen && <img src={m.imagen} alt="Captura enviada" />}
                            {m.archivo && <span className="burbuja-archivo"><Icono nombre="archivo" tamano={16} /> {m.archivo}</span>}
                            {m.audio && <audio src={m.audio} controls preload="metadata" />}
                            {m.texto && <p><TextoWhatsApp texto={m.texto} /></p>}
                            <time>{m.hora}{m.de === 'yo' && ' ✓✓'}</time>
                        </div>
                    ))}
                    {escribiendo && (
                        <div className="burbuja bot escribiendo" aria-label="El asistente está escribiendo">
                            <span /><span /><span />
                        </div>
                    )}
                    <div ref={fin} />
                </div>

                {opciones.length > 0 && !escribiendo && (
                    <div className="chat-opciones">
                        {opciones.map((nombre, i) => (
                            <button key={nombre} type="button" onClick={() => enviar({ visible: { texto: String(i + 1) }, cuerpo: { texto: String(i + 1) } })}>
                                {i + 1}. {nombre}
                            </button>
                        ))}
                        <button type="button" className="opcion-ubicacion" onClick={compartirUbicacion}>
                            <Icono nombre="pin" tamano={14} /> Compartir ubicación
                        </button>
                    </div>
                )}

                {error && <p className="chat-error"><Icono nombre="alerta" tamano={14} /> {error}</p>}

                <form className="chat-barra" onSubmit={enviarTexto}>
                    <button type="button" className="chat-boton-icono" onClick={() => inputArchivo.current?.click()}
                        disabled={escribiendo} aria-label="Adjuntar captura o PDF">
                        <Icono nombre="clip" tamano={20} />
                    </button>
                    <input ref={inputArchivo} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf" hidden
                        onChange={e => { enviarArchivo(e.target.files[0]); e.target.value = '' }} />
                    <input className="chat-entrada" value={texto} onChange={e => setTexto(e.target.value)}
                        placeholder="Pega el mensaje sospechoso, o escribe: estado · escuchar" aria-label="Mensaje" disabled={escribiendo} />
                    {texto.trim()
                        ? <button type="submit" className="chat-boton-icono enviar" aria-label="Enviar" disabled={escribiendo}><Icono nombre="flecha" tamano={20} /></button>
                        : <GrabadorVoz compacto onListo={enviarVoz} deshabilitado={escribiendo} />}
                </form>
            </div>
        </div>
    )
}
