import { useEffect, useRef, useState } from 'react'
import Icono from './Icono.jsx'

const MAX_SEGUNDOS = 60
const FRECUENCIA = 16000 // voz: 16 kHz mono es suficiente y pesa ~32 KB por segundo

/** PCM mono Float32 → archivo WAV 16-bit. */
function codificarWav(muestras, frecuencia) {
    const buffer = new ArrayBuffer(44 + muestras.length * 2)
    const vista = new DataView(buffer)
    const texto = (pos, s) => [...s].forEach((c, i) => vista.setUint8(pos + i, c.charCodeAt(0)))
    texto(0, 'RIFF'); vista.setUint32(4, 36 + muestras.length * 2, true); texto(8, 'WAVE')
    texto(12, 'fmt '); vista.setUint32(16, 16, true); vista.setUint16(20, 1, true); vista.setUint16(22, 1, true)
    vista.setUint32(24, frecuencia, true); vista.setUint32(28, frecuencia * 2, true)
    vista.setUint16(32, 2, true); vista.setUint16(34, 16, true)
    texto(36, 'data'); vista.setUint32(40, muestras.length * 2, true)
    for (let i = 0; i < muestras.length; i++) {
        const s = Math.max(-1, Math.min(1, muestras[i]))
        vista.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return new Uint8Array(buffer)
}

/** Lo que grabe el navegador (webm/ogg/mp4) → WAV 16 kHz mono, formato que acepta la IA. */
async function aWav(blob) {
    const Contexto = window.AudioContext || window.webkitAudioContext
    const contexto = new Contexto()
    const audio = await contexto.decodeAudioData(await blob.arrayBuffer())
    contexto.close()
    const largo = Math.ceil(audio.duration * FRECUENCIA)
    const offline = new OfflineAudioContext(1, largo, FRECUENCIA)
    const fuente = offline.createBufferSource()
    fuente.buffer = audio
    fuente.connect(offline.destination)
    fuente.start()
    const remuestreado = await offline.startRendering()
    return codificarWav(remuestreado.getChannelData(0), FRECUENCIA)
}

function aBase64(bytes) {
    let binario = ''
    for (let i = 0; i < bytes.length; i += 0x8000) binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    return btoa(binario)
}

/**
 * Botón de nota de voz: para quien prefiere contar lo que pasó en vez de escribir.
 * onListo({ nombre, mime, base64, tamano, url })
 */
export default function GrabadorVoz({ onListo, deshabilitado }) {
    const [estado, setEstado] = useState('inactivo') // inactivo | grabando | procesando
    const [segundos, setSegundos] = useState(0)
    const [error, setError] = useState(null)
    const grabador = useRef(null)
    const temporizador = useRef(null)

    useEffect(() => () => {
        clearInterval(temporizador.current)
        grabador.current?.stream.getTracks().forEach(t => t.stop())
    }, [])

    const iniciar = async () => {
        setError(null)
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
            setError('Tu navegador no permite grabar audio. Puedes mandar la nota de voz por WhatsApp.')
            return
        }
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            const partes = []
            const rec = new MediaRecorder(stream)
            rec.ondataavailable = e => e.data.size && partes.push(e.data)
            rec.onstop = async () => {
                clearInterval(temporizador.current)
                stream.getTracks().forEach(t => t.stop())
                setEstado('procesando')
                try {
                    const wav = await aWav(new Blob(partes, { type: rec.mimeType }))
                    onListo({
                        nombre: `nota_de_voz_${new Date().toISOString().slice(11, 19).replace(/:/g, '')}.wav`,
                        mime: 'audio/wav',
                        base64: aBase64(wav),
                        tamano: wav.length,
                        url: URL.createObjectURL(new Blob([wav], { type: 'audio/wav' })),
                    })
                } catch {
                    setError('No pudimos procesar la grabación. Inténtalo de nuevo.')
                }
                setEstado('inactivo')
            }
            grabador.current = rec
            rec.start()
            setSegundos(0)
            setEstado('grabando')
            temporizador.current = setInterval(() => {
                setSegundos(s => {
                    if (s + 1 >= MAX_SEGUNDOS) rec.state === 'recording' && rec.stop()
                    return s + 1
                })
            }, 1000)
        } catch {
            setError('Necesitamos permiso para usar el micrófono.')
        }
    }

    const detener = () => grabador.current?.state === 'recording' && grabador.current.stop()

    return (
        <div className="grabador">
            {estado === 'grabando' ? (
                <button type="button" className="boton boton-grabando" onClick={detener}>
                    <span className="punto-grabando" /> Grabando {segundos}s / {MAX_SEGUNDOS}s · <Icono nombre="detener" tamano={15} /> Terminar
                </button>
            ) : (
                <button type="button" className="boton boton-secundario boton-voz" onClick={iniciar}
                    disabled={deshabilitado || estado === 'procesando'}>
                    {estado === 'procesando'
                        ? <><span className="spinner" /> Preparando audio…</>
                        : <><Icono nombre="microfono" tamano={17} /> Contarlo con una nota de voz</>}
                </button>
            )}
            {error && <p className="aviso aviso-error"><Icono nombre="alerta" tamano={16} /> {error}</p>}
        </div>
    )
}
