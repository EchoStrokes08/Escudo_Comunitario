import { useRef, useState } from 'react'
import { UPZ_BOSA, obtenerUpzMasCercana } from '../data/upz.js'
import { dentroDeBosa } from '../data/bosaPolygon.js'
import { nivelRiesgo } from '../utils/riesgo.js'

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

// Límites espejo del backend (variables MAX_ARCHIVOS / MAX_PESO_MB)
const MAX_ARCHIVOS = 3
const MAX_PESO_MB = 2
const MAX_PESO_BYTES = MAX_PESO_MB * 1024 * 1024

const MIME_SOPORTADOS = ['application/pdf', 'text/plain', 'image/png', 'image/jpeg']
const EXTENSIONES = ['.pdf', '.txt', '.png', '.jpg', '.jpeg']

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

    // Estados de geolocalización del dispositivo
    const [cargandoGps, setCargandoGps] = useState(false)
    const [gpsInfo, setGpsInfo] = useState(null) // { lat, lng, enBosa }
    const [errorGps, setErrorGps] = useState(null)

    const inputArchivo = useRef(null)

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
                setErrorArchivo(`"${archivo.name}": formato no soportado. Adjunta PDF, TXT, PNG o JPEG.`)
                continue
            }
            if (archivo.size > MAX_PESO_BYTES) {
                setErrorArchivo(
                    `"${archivo.name}" pesa ${(archivo.size / 1_048_576).toFixed(1)} MB. ` +
                    `El máximo es ${MAX_PESO_MB} MB: comprime la imagen o usa un archivo más pequeño.`
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
                })
            } catch (err) {
                setErrorArchivo(err.message)
            }
        }

        if (nuevos.length) setAdjuntos(prev => [...prev, ...nuevos].slice(0, MAX_ARCHIVOS))
    }

    const eliminarAdjunto = (indice) => {
        setAdjuntos(prev => prev.filter((_, i) => i !== indice))
        setErrorArchivo(null)
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
            setError('Pega el mensaje completo o adjunta un archivo (mínimo 10 caracteres de texto).')
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
                        Pega el mensaje sospechoso o adjunta una captura de pantalla,
                        factura o PDF. Nuestra IA lee el archivo, lo cruza con tu texto
                        y te entrega un certificado trazable.
                    </p>
                </div>
            </section>

            <form className="formulario" onSubmit={enviar}>
                <label htmlFor="mensaje">
                    Mensaje sospechoso <span className="obligatorio">(texto)</span>
                </label>
                <textarea
                    id="mensaje"
                    rows={5}
                    placeholder="Ej: Felicidades, ganaste un premio de $5.000.000 en la lotería Bogotá. Ingresa aquí www.premios-bogota.top y consigna el impuesto en Nequi 3001234567 antes de las 6pm…"
                    value={mensaje}
                    onChange={e => setMensaje(e.target.value)}
                />

                <label>
                    Archivos adjuntos <span className="obligatorio">
                        (PDF, TXT, PNG o JPEG · máx. {MAX_PESO_MB} MB · {MAX_ARCHIVOS} archivos)
                    </span>
                </label>

                <div
                    className={`zona-arrastre ${arrastrando ? 'arrastrando' : ''}`}
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
                    <span className="zona-arrastre-icono">📄</span>
                    <span>
                        Arrastra aquí tu captura o factura, o{' '}
                        <strong>haz clic para seleccionar</strong>
                    </span>
                    <input
                        ref={inputArchivo}
                        type="file"
                        multiple
                        accept=".pdf,.txt,.png,.jpg,.jpeg"
                        hidden
                        onChange={e => {
                            agregarArchivos(e.target.files)
                            e.target.value = ''
                        }}
                    />
                </div>

                {errorArchivo && <p className="error">⚠️ {errorArchivo}</p>}

                {adjuntos.length > 0 && (
                    <ul className="lista-adjuntos">
                        {adjuntos.map((a, i) => (
                            <li key={`${a.nombre}-${i}`} className="adjunto">
                                {a.preview
                                    ? <img src={a.preview} alt={a.nombre} className="adjunto-miniatura" />
                                    : <span className="adjunto-icono">{a.mime === 'application/pdf' ? '📕' : '📜'}</span>}
                                <span className="adjunto-info">
                                    <strong>{a.nombre}</strong>
                                    <small>{(a.tamano / 1024).toFixed(0)} KB</small>
                                </span>
                                <button
                                    type="button"
                                    className="adjunto-eliminar"
                                    title="Quitar archivo"
                                    onClick={() => eliminarAdjunto(i)}
                                >✕</button>
                            </li>
                        ))}
                    </ul>
                )}

                {/* 1. Selector de las 5 UPZ de Bosa */}
                <label htmlFor="upz">
                    Unidad de Planeamiento Zonal (UPZ) de Bosa{' '}
                    <span className="obligatorio">(5 UPZ distritales)</span>
                </label>
                <select id="upz" value={upz} onChange={e => setUpz(e.target.value)}>
                    <option value="">Selecciona tu UPZ…</option>
                    {UPZ_BOSA.map(u => (
                        <option key={u.nombre} value={u.nombre}>
                            {u.codigo}: {u.nombre} ({u.sectores})
                        </option>
                    ))}
                </select>

                {/* 2. Caja interactiva de Geolocalización del Dispositivo */}
                <div className="geo-caja">
                    <div className="geo-cabecera">
                        <div>
                            <span className="geo-titulo">📍 Ubicación del dispositivo (GPS)</span>
                            <p className="texto-suave geo-descripcion">
                                Opcional: si estás dentro de Bosa se tomará tu punto exacto; si estás en otra localidad, se usará como referencia la UPZ seleccionada para proteger el mapa de calor comunitario.
                            </p>
                        </div>
                        <button
                            type="button"
                            className="boton boton-secundario geo-boton"
                            onClick={obtenerUbicacionDispositivo}
                            disabled={cargandoGps}
                        >
                            {cargandoGps ? '⏳ Consultando GPS…' : (gpsInfo ? '🔄 Actualizar GPS' : '📍 Obtener mi ubicación')}
                        </button>
                    </div>

                    {errorGps && (
                        <div className="geo-alerta geo-alerta-error">
                            ⚠️ {errorGps} Se georreferenciará mediante la UPZ seleccionada.
                        </div>
                    )}

                    {gpsInfo && (
                        <div className={`geo-alerta ${gpsInfo.enBosa ? 'geo-alerta-exito' : 'geo-alerta-aviso'}`}>
                            <div className="geo-alerta-contenido">
                                {gpsInfo.enBosa ? (
                                    <>
                                        <strong>🎯 Ubicación precisa dentro de Bosa verificada</strong>
                                        <span>Coordenadas GPS: {gpsInfo.lat}, {gpsInfo.lng}. Se enviará tu punto exacto para máxima fidelidad en el mapa de calor.</span>
                                    </>
                                ) : (
                                    <>
                                        <strong>⚠️ Dispositivo ubicado fuera de Bosa</strong>
                                        <span>Coordenadas detectadas: {gpsInfo.lat}, {gpsInfo.lng}. Para evitar distorsionar el mapa de calor comunitario de Bosa, tus coordenadas externas no se usarán y el reporte se ubicará en la <strong>UPZ {upz || 'seleccionada'}</strong>.</span>
                                    </>
                                )}
                            </div>
                            <button
                                type="button"
                                className="geo-limpiar-btn"
                                onClick={limpiarUbicacion}
                                title="Descartar ubicación GPS"
                            >
                                ✕
                            </button>
                        </div>
                    )}
                </div>

                <button className="boton boton-primario" type="submit" disabled={cargando}>
                    {cargando
                        ? '🔍 Analizando tu mensaje y tus archivos…'
                        : 'Analizar y reportar'}
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

                    {resultado.adjuntos_analizados > 0 && (
                        <div className="adjuntos-analizados">
                            <h4>📎 Archivos analizados ({resultado.adjuntos_analizados})</h4>
                            {resultado.adjuntos.map((a, i) => (
                                <p key={i}>
                                    <strong>{a.nombre}</strong> · {a.mime} · {(a.tamano / 1024).toFixed(0)} KB
                                    <br />
                                    <small>SHA-256: {a.sha256.slice(0, 32)}…</small>
                                </p>
                            ))}
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
                            Registrado en Bosa · UPZ {resultado.upz || resultado.barrio}
                            {resultado.ubicacion_dispositivo_en_bosa ? ' (🎯 Ubicación GPS precisa en Bosa)' : ' (📍 Ubicación por UPZ zonal)'} ·{' '}
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
