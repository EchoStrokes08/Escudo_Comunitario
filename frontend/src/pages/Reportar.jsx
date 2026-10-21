import { useEffect, useMemo, useRef, useState } from 'react'
import { UPZ_BOSA, obtenerUpzMasCercana } from '../data/upz.js'
import { dentroDeBosa } from '../data/bosaPolygon.js'
import Icono from '../components/Icono.jsx'
import GrabadorVoz from '../components/GrabadorVoz.jsx'
import Veredicto from '../components/Veredicto.jsx'
import { API_URL } from '../services/api.js'

// Límites espejo del backend (variables MAX_ARCHIVOS / MAX_PESO_MB / MAX_PESO_AUDIO_MB)
const MAX_ARCHIVOS = 3
const MAX_PESO_MB = 2
const MAX_PESO_AUDIO_MB = 4
const pesoMaximo = (mime) => (mime.startsWith('audio/') ? MAX_PESO_AUDIO_MB : MAX_PESO_MB) * 1024 * 1024

const MIME_SOPORTADOS = ['application/pdf', 'text/plain', 'image/png', 'image/jpeg', 'image/webp',
    'audio/ogg', 'audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/wave']
const EXTENSIONES = ['.pdf', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.ogg', '.opus', '.mp3', '.wav']

// Pista visual mientras se escribe; el veredicto real lo calcula el backend
const SENALES = [
    { id: 'enlace', etiqueta: 'Enlace', patron: /(https?:\/\/|www\.|\b[\w-]+\.(top|xyz|site|online|link|info|click|co|com|net)\b)/i },
    { id: 'dinero', etiqueta: 'Dinero o premio', patron: /(\$\s?\d|millones|pesos|premio|ganaste|ganador|sorteo|subsidio)/i },
    { id: 'urgencia', etiqueta: 'Urgencia', patron: /(urgente|inmediat|antes de las|hoy mismo|última oportunidad|ultima oportunidad|expira|vence|bloquead|suspendid)/i },
    { id: 'pago', etiqueta: 'Pide pago o datos', patron: /(nequi|daviplata|consign|transfier|transferencia|clave|contraseña|código|codigo|pin\b|cuenta)/i },
    { id: 'telefono', etiqueta: 'Número de celular', patron: /\b3\d{2}[\s-]?\d{3}[\s-]?\d{4}\b/ },
]

const PASOS_ANALISIS = [
    'Leyendo el mensaje…',
    'Extrayendo texto de los archivos…',
    'Buscando señales de fraude con IA…',
    'Consultando registros de dominios y reportes de la comunidad…',
    'Calculando la confianza del veredicto…',
    'Encadenando el certificado y sellándolo en Bitcoin…',
]

function extensionValida(nombre) {
    const punto = nombre.lastIndexOf('.')
    return punto > 0 && EXTENSIONES.includes(nombre.slice(punto).toLowerCase())
}

function leerComoBase64(archivo) {
    return new Promise((resolve, reject) => {
        const lector = new FileReader()
        lector.onload = () => resolve(String(lector.result).split(',')[1]) // sin prefijo data:
        lector.onerror = () => reject(new Error(`No se pudo leer "${archivo.name}".`))
        lector.readAsDataURL(archivo)
    })
}

export default function Reportar() {
    const [mensaje, setMensaje] = useState('')
    const [upz, setUpz] = useState('')
    const [adjuntos, setAdjuntos] = useState([])
    const [arrastrando, setArrastrando] = useState(false)
    const [errorArchivo, setErrorArchivo] = useState(null)
    const [error, setError] = useState(null)
    const [cargando, setCargando] = useState(false)
    const [resultado, setResultado] = useState(null)
    const [pasoAnalisis, setPasoAnalisis] = useState(0)

    // Estados de geolocalización del dispositivo
    const [cargandoGps, setCargandoGps] = useState(false)
    const [gpsInfo, setGpsInfo] = useState(null) // { lat, lng, enBosa }
    const [errorGps, setErrorGps] = useState(null)

    const inputArchivo = useRef(null)
    const seccionResultado = useRef(null)

    const senales = useMemo(() => SENALES.filter(s => s.patron.test(mensaje)), [mensaje])

    // Rota los mensajes de progreso mientras el backend analiza
    useEffect(() => {
        if (!cargando) return
        setPasoAnalisis(0)
        const id = setInterval(() => setPasoAnalisis(p => Math.min(p + 1, PASOS_ANALISIS.length - 1)), 1300)
        return () => clearInterval(id)
    }, [cargando])

    useEffect(() => {
        if (resultado) seccionResultado.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, [resultado])

    const agregarArchivos = async (lista) => {
        setErrorArchivo(null)
        const archivos = Array.from(lista)
        const disponibles = MAX_ARCHIVOS - adjuntos.length

        if (archivos.length > disponibles) {
            setErrorArchivo(`Máximo ${MAX_ARCHIVOS} archivos por reporte. Solo puedes adjuntar ${disponibles} más.`)
        }

        const nuevos = []
        for (const archivo of archivos.slice(0, disponibles)) {
            if (!MIME_SOPORTADOS.includes(archivo.type) || !extensionValida(archivo.name)) {
                setErrorArchivo(`"${archivo.name}": formato no soportado. Adjunta una captura, PDF, TXT o audio (OGG, MP3, WAV).`)
                continue
            }
            if (archivo.size > pesoMaximo(archivo.type)) {
                setErrorArchivo(
                    `"${archivo.name}" pesa ${(archivo.size / 1_048_576).toFixed(1)} MB. ` +
                    `El máximo es ${pesoMaximo(archivo.type) / 1_048_576} MB: usa un archivo más pequeño.`
                )
                continue
            }
            try {
                const base64 = await leerComoBase64(archivo)
                nuevos.push({
                    nombre: archivo.name,
                    mime: archivo.type,
                    base64,
                    tamano: archivo.size,
                    preview: archivo.type.startsWith('image/')
                        ? `data:${archivo.type};base64,${base64}`
                        : null,
                    audio: archivo.type.startsWith('audio/') ? URL.createObjectURL(archivo) : null,
                })
            } catch (err) {
                setErrorArchivo(err.message)
            }
        }

        if (nuevos.length) setAdjuntos(prev => [...prev, ...nuevos].slice(0, MAX_ARCHIVOS))
    }

    const agregarNotaVoz = (nota) => {
        setErrorArchivo(null)
        if (adjuntos.length >= MAX_ARCHIVOS) {
            setErrorArchivo(`Máximo ${MAX_ARCHIVOS} archivos por reporte. Quita uno para agregar la nota de voz.`)
            return
        }
        setAdjuntos(prev => [...prev, { ...nota, preview: null, audio: nota.url }])
    }

    const eliminarAdjunto = (indice) => {
        setAdjuntos(prev => prev.filter((_, i) => i !== indice))
        setErrorArchivo(null)
    }

    const pegarDelPortapapeles = async () => {
        try {
            const texto = await navigator.clipboard.readText()
            if (texto) setMensaje(texto)
        } catch {
            setError('No pudimos leer el portapapeles. Pega el mensaje manualmente (Ctrl + V).')
        }
    }

    const obtenerUbicacionDispositivo = () => {
        if (!navigator.geolocation) {
            setErrorGps('Tu navegador o dispositivo no soporta geolocalización GPS.')
            return
        }

        setCargandoGps(true)
        setErrorGps(null)

        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = Number(pos.coords.latitude.toFixed(6))
                const lng = Number(pos.coords.longitude.toFixed(6))
                const enBosa = dentroDeBosa(lat, lng)

                setGpsInfo({ lat, lng, enBosa })
                setCargandoGps(false)

                // Si está dentro de Bosa y el usuario aún no seleccionó UPZ, sugerir la más cercana
                if (enBosa && !upz) {
                    const sugerida = obtenerUpzMasCercana(lat, lng)
                    if (sugerida) {
                        setUpz(sugerida.nombre)
                    }
                }
            },
            (err) => {
                let msg = 'No se pudo obtener la ubicación GPS.'
                if (err.code === 1) msg = 'Permiso de ubicación denegado por el usuario.'
                else if (err.code === 2) msg = 'Ubicación no disponible en tu dispositivo.'
                else if (err.code === 3) msg = 'Tiempo de espera agotado al consultar GPS.'
                setErrorGps(msg)
                setCargandoGps(false)
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
        )
    }

    const limpiarUbicacion = () => {
        setGpsInfo(null)
        setErrorGps(null)
    }

    const enviar = async (e) => {
        e.preventDefault()
        setError(null)

        if (mensaje.trim().length < 10 && adjuntos.length === 0) {
            setError('Pega el mensaje completo, adjunta una captura o graba una nota de voz.')
            return
        }

        setCargando(true)
        setResultado(null)

        try {
            // Regla: si el dispositivo está dentro de Bosa, se envían sus coordenadas precisas;
            // si está fuera de Bosa, se omiten coordenadas (null) para no sesgar el mapa de calor.
            const latEnvio = (gpsInfo && gpsInfo.enBosa) ? gpsInfo.lat : null
            const lngEnvio = (gpsInfo && gpsInfo.enBosa) ? gpsInfo.lng : null
            const upzEnvio = upz || (gpsInfo?.enBosa ? obtenerUpzMasCercana(gpsInfo.lat, gpsInfo.lng).nombre : 'Bosa Central')

            const respuesta = await fetch(`${API_URL}/api/reporte-web`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mensaje: mensaje.trim(),
                    upz: upzEnvio,
                    barrio: upzEnvio,
                    lat: latEnvio,
                    lng: lngEnvio,
                    adjuntos: adjuntos.map(({ nombre, mime, base64 }) => ({ nombre, mime, base64 })),
                }),
            })

            if (!respuesta.ok) {
                const detalle = await respuesta.json().catch(() => null)
                throw new Error(detalle?.detail || `El servicio respondió con error (${respuesta.status}).`)
            }

            setResultado(await respuesta.json())
        } catch (err) {
            // fetch lanza TypeError ("NetworkError…", "Failed to fetch") cuando no llega al servidor
            setError(err instanceof TypeError
                ? 'No pudimos conectar con el servidor de análisis. Verifica tu conexión o que el backend esté en línea e inténtalo de nuevo.'
                : err.message || 'No se pudo enviar el reporte. Verifica tu conexión.')
        } finally {
            setCargando(false)
        }
    }

    const nuevoReporte = () => {
        setMensaje('')
        setUpz('')
        setAdjuntos([])
        setResultado(null)
        setError(null)
        setErrorArchivo(null)
        limpiarUbicacion()
        window.scrollTo({ top: 0, behavior: 'smooth' })
    }

    const listo = mensaje.trim().length >= 10 || adjuntos.length > 0
    const pasoUnoListo = mensaje.trim().length >= 10 || adjuntos.some(a => a.audio)

    return (
        <div className="pagina-reporte">
            <section className="hero hero-compacto">
                <div className="hero-texto">
                    <span className="eyebrow"><Icono nombre="escudo" tamano={14} /> Canal de denuncia ciudadana</span>
                    <h1>¿Te llegó un mensaje raro?</h1>
                    <p>
                        Pégalo, sube una captura o <strong>cuéntalo con tu voz</strong>. Nuestra IA lo analiza,
                        lo verifica en fuentes abiertas en tiempo real, te dice qué hacer y te entrega un
                        certificado sellado que nadie puede alterar.
                    </p>
                </div>
            </section>

            <div className="rejilla-reporte">
                <form className="formulario" onSubmit={enviar}>
                    {/* Paso 1: mensaje */}
                    <fieldset className={`paso ${pasoUnoListo ? 'paso-completo' : ''}`}>
                        <legend className="paso-titulo">
                            <span className="paso-numero">{pasoUnoListo ? <Icono nombre="check" tamano={14} grosor={2.4} /> : 1}</span>
                            El mensaje sospechoso
                        </legend>

                        <div className="campo-texto">
                            <textarea
                                id="mensaje"
                                rows={6}
                                placeholder="Ej: Felicidades, ganaste un premio de $5.000.000 en la lotería Bogotá. Ingresa aquí www.premios-bogota.top y consigna el impuesto en Nequi 3001234567 antes de las 6pm…"
                                value={mensaje}
                                onChange={e => setMensaje(e.target.value)}
                                aria-label="Mensaje sospechoso"
                            />
                            <div className="campo-texto-pie">
                                <button type="button" className="boton-texto" onClick={pegarDelPortapapeles}>
                                    <Icono nombre="portapapeles" tamano={15} /> Pegar
                                </button>
                                <span className="texto-suave">{mensaje.length} caracteres</span>
                            </div>
                        </div>

                        <div className="senales" aria-live="polite">
                            {senales.length > 0 ? (
                                <>
                                    <span className="senales-titulo"><Icono nombre="chispa" tamano={14} /> Señales que vemos:</span>
                                    {senales.map(s => <span key={s.id} className="senal">{s.etiqueta}</span>)}
                                </>
                            ) : (
                                <span className="texto-suave">Mientras escribes, te mostramos las señales típicas de fraude que detectemos.</span>
                            )}
                        </div>

                        <div className="separador-o"><span>o si prefieres hablar</span></div>
                        <GrabadorVoz onListo={agregarNotaVoz} deshabilitado={cargando} />
                    </fieldset>

                    {/* Paso 2: evidencia */}
                    <fieldset className={`paso ${adjuntos.length ? 'paso-completo' : ''}`}>
                        <legend className="paso-titulo">
                            <span className="paso-numero">{adjuntos.length ? <Icono nombre="check" tamano={14} grosor={2.4} /> : 2}</span>
                            Evidencia <span className="opcional">opcional</span>
                        </legend>

                        <div
                            className={`zona-arrastre ${arrastrando ? 'arrastrando' : ''} ${adjuntos.length >= MAX_ARCHIVOS ? 'llena' : ''}`}
                            onDragOver={e => { e.preventDefault(); setArrastrando(true) }}
                            onDragLeave={() => setArrastrando(false)}
                            onDrop={e => {
                                e.preventDefault()
                                setArrastrando(false)
                                agregarArchivos(e.dataTransfer.files)
                            }}
                            onClick={() => inputArchivo.current?.click()}
                            role="button"
                            tabIndex={0}
                            onKeyDown={e => e.key === 'Enter' && inputArchivo.current?.click()}
                        >
                            <span className="zona-arrastre-icono"><Icono nombre="subir" tamano={22} /></span>
                            <span>
                                Arrastra tu captura o factura, o <strong>selecciona un archivo</strong>
                            </span>
                            <small>Captura, PDF, TXT o audio · máx. {MAX_PESO_MB} MB ({MAX_PESO_AUDIO_MB} MB audio) · {adjuntos.length}/{MAX_ARCHIVOS} archivos</small>
                            <input
                                ref={inputArchivo}
                                type="file"
                                multiple
                                accept={EXTENSIONES.join(',')}
                                hidden
                                onChange={e => {
                                    agregarArchivos(e.target.files)
                                    e.target.value = ''
                                }}
                            />
                        </div>

                        {errorArchivo && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {errorArchivo}</p>}

                        {adjuntos.length > 0 && (
                            <ul className="lista-adjuntos">
                                {adjuntos.map((a, i) => (
                                    <li key={`${a.nombre}-${i}`} className="adjunto">
                                        {a.preview
                                            ? <img src={a.preview} alt={a.nombre} className="adjunto-miniatura" />
                                            : <span className="adjunto-icono"><Icono nombre={a.audio ? 'microfono' : 'archivo'} tamano={20} /></span>}
                                        <span className="adjunto-info">
                                            <strong>{a.audio ? 'Nota de voz' : a.nombre}</strong>
                                            {a.audio
                                                ? <audio src={a.audio} controls preload="metadata" className="adjunto-audio" />
                                                : <small>{a.mime === 'application/pdf' ? 'PDF' : a.mime.split('/')[1].toUpperCase()} · {(a.tamano / 1024).toFixed(0)} KB</small>}
                                        </span>
                                        <button
                                            type="button"
                                            className="adjunto-eliminar"
                                            title="Quitar archivo"
                                            onClick={() => eliminarAdjunto(i)}
                                        ><Icono nombre="cerrar" tamano={14} /></button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </fieldset>

                    {/* Paso 3: ubicación */}
                    <fieldset className={`paso ${upz ? 'paso-completo' : ''}`}>
                        <legend className="paso-titulo">
                            <span className="paso-numero">{upz ? <Icono nombre="check" tamano={14} grosor={2.4} /> : 3}</span>
                            ¿Dónde vives o te llegó?
                        </legend>

                        <div className="selector-upz" role="radiogroup" aria-label="Unidad de Planeamiento Zonal de Bosa">
                            {UPZ_BOSA.map(u => (
                                <button
                                    key={u.nombre}
                                    type="button"
                                    role="radio"
                                    aria-checked={upz === u.nombre}
                                    className={`opcion-upz ${upz === u.nombre ? 'activa' : ''}`}
                                    onClick={() => setUpz(upz === u.nombre ? '' : u.nombre)}
                                    title={u.sectores}
                                >
                                    <span className="opcion-upz-codigo">{u.codigo}</span>
                                    <strong>{u.nombre}</strong>
                                    <small>{u.sectores}</small>
                                </button>
                            ))}
                        </div>

                        <div className="geo-caja">
                            <div className="geo-cabecera">
                                <span className="geo-icono"><Icono nombre="mira" tamano={18} /></span>
                                <div>
                                    <span className="geo-titulo">Ubicación del dispositivo <span className="opcional">opcional</span></span>
                                    <p className="geo-descripcion">
                                        Si estás dentro de Bosa usamos tu punto exacto. Si estás en otra localidad,
                                        usamos la UPZ elegida para no distorsionar el mapa comunitario.
                                    </p>
                                </div>
                                <button
                                    type="button"
                                    className="boton boton-secundario geo-boton"
                                    onClick={obtenerUbicacionDispositivo}
                                    disabled={cargandoGps}
                                >
                                    {cargandoGps
                                        ? <><span className="spinner" /> Consultando…</>
                                        : gpsInfo
                                            ? <><Icono nombre="recargar" tamano={15} /> Actualizar</>
                                            : <><Icono nombre="pin" tamano={15} /> Usar mi ubicación</>}
                                </button>
                            </div>

                            {errorGps && (
                                <div className="aviso aviso-error">
                                    <Icono nombre="alerta" tamano={16} />
                                    <span>{errorGps} Se georreferenciará mediante la UPZ seleccionada.</span>
                                </div>
                            )}

                            {gpsInfo && (
                                <div className={`aviso ${gpsInfo.enBosa ? 'aviso-exito' : 'aviso-medio'}`}>
                                    <Icono nombre={gpsInfo.enBosa ? 'check' : 'alerta'} tamano={16} />
                                    <div className="aviso-contenido">
                                        {gpsInfo.enBosa ? (
                                            <>
                                                <strong>Ubicación precisa dentro de Bosa verificada</strong>
                                                <span>{gpsInfo.lat}, {gpsInfo.lng} · se enviará tu punto exacto al mapa de calor.</span>
                                            </>
                                        ) : (
                                            <>
                                                <strong>Tu dispositivo está fuera de Bosa</strong>
                                                <span>{gpsInfo.lat}, {gpsInfo.lng} · no usaremos estas coordenadas; el reporte se ubicará en la <strong>UPZ {upz || 'seleccionada'}</strong>.</span>
                                            </>
                                        )}
                                    </div>
                                    <button type="button" className="aviso-cerrar" onClick={limpiarUbicacion} title="Descartar ubicación GPS">
                                        <Icono nombre="cerrar" tamano={14} />
                                    </button>
                                </div>
                            )}
                        </div>
                    </fieldset>

                    <div className="envio">
                        <button className={`boton boton-primario boton-grande boton-enviar ${cargando ? 'analizando' : ''}`} type="submit" disabled={cargando}>
                            {cargando
                                ? <><span className="spinner" /> <span key={pasoAnalisis} className="paso-analisis">{PASOS_ANALISIS[pasoAnalisis]}</span></>
                                : <><Icono nombre="escudo" /> Analizar y reportar</>}
                        </button>
                        {!listo && !cargando && <span className="texto-suave envio-ayuda">Escribe el mensaje o adjunta un archivo para continuar.</span>}
                        {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}
                    </div>
                </form>

                <aside className="guia">
                    <div className="panel guia-panel">
                        <h2>Cómo reconocer un fraude</h2>
                        <ul className="guia-lista">
                            <li><span className="guia-icono fondo-alto-suave"><Icono nombre="reloj" tamano={16} /></span><div><strong>Te apuran</strong><p>“Antes de las 6 pm”, “tu cuenta será bloqueada”. La prisa es la herramienta principal del estafador.</p></div></li>
                            <li><span className="guia-icono fondo-medio-suave"><Icono nombre="chispa" tamano={16} /></span><div><strong>Premios que no pediste</strong><p>Loterías, subsidios o rifas en las que nunca participaste.</p></div></li>
                            <li><span className="guia-icono fondo-bajo-suave"><Icono nombre="clip" tamano={16} /></span><div><strong>Enlaces extraños</strong><p>Dominios como <code>.top</code>, <code>.xyz</code> o nombres que imitan a bancos y entidades.</p></div></li>
                            <li><span className="guia-icono fondo-alto-suave"><Icono nombre="hash" tamano={16} /></span><div><strong>Piden pagos o claves</strong><p>Ninguna entidad seria te pide consignar a un Nequi personal ni tu código de verificación.</p></div></li>
                        </ul>
                    </div>
                    <div className="panel guia-panel guia-nota">
                        <Icono nombre="escudo" tamano={20} />
                        <p>Tu reporte es anónimo. En el panel público solo se ve una versión sin datos personales; los archivos se guardan como huella SHA-256.</p>
                    </div>
                </aside>
            </div>

            {resultado && <Veredicto resultado={resultado} onNuevo={nuevoReporte} />}
        </div>
    )
}
