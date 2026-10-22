import { useState } from 'react'
import Icono from '../components/Icono.jsx'
import CodigoQR from '../components/CodigoQR.jsx'
import { TELEGRAM_BOT, URL_TELEGRAM, URL_WHATSAPP, WHATSAPP_VISIBLE } from '../utils/canales.js'

const PASOS = [
    { icono: 'mensaje', titulo: 'Reenvía', texto: 'el mensaje, una foto de la pantalla o cuéntalo en una nota de voz' },
    { icono: 'escudo', titulo: 'Te decimos', texto: 'si es fraude y qué hacer ahora, por escrito y en audio' },
    { icono: 'candado', titulo: 'Recibe', texto: 'un certificado de tu reporte para denunciar y seguir tu caso' },
]

/**
 * Cartel imprimible (carta / A4) para tiendas, droguerías, conjuntos y salones comunales:
 * quien no sabe "entrar a una página" solo escanea el QR con la cámara.
 */
export default function Cartel() {
    const [lugar, setLugar] = useState('')
    const urlChat = `${window.location.origin}/chat`

    return (
        <div className="pagina-cartel">
            <div className="acciones-certificado no-imprimir">
                <label className="campo-cartel">
                    <span>Nombre del lugar (opcional)</span>
                    <input value={lugar} onChange={e => setLugar(e.target.value)} maxLength={48} placeholder="Ej. Tienda Don Luis · Bosa La Libertad" />
                </label>
                <button type="button" className="boton boton-primario" onClick={() => window.print()}><Icono nombre="imprimir" /> Imprimir cartel</button>
            </div>

            <article className="cartel">
                <header className="cartel-cabecera">
                    <Icono nombre="escudo" tamano={46} grosor={2} />
                    <div>
                        <strong>Escudo Comunitario</strong>
                        <span>Bosa contra el fraude digital</span>
                    </div>
                </header>

                <h1>¿Te llegó un mensaje <em>raro</em>?</h1>
                <p className="cartel-sub">Antes de consignar, dar un código o abrir un enlace: <strong>pregúntanos gratis</strong>.</p>

                <ol className="cartel-pasos">
                    {PASOS.map((p, i) => (
                        <li key={p.titulo}>
                            <span className="cartel-paso-icono"><Icono nombre={p.icono} tamano={30} grosor={2} /></span>
                            <span className="cartel-paso-numero">{i + 1}</span>
                            <strong>{p.titulo}</strong>
                            <span>{p.texto}</span>
                        </li>
                    ))}
                </ol>

                <div className="cartel-qrs">
                    <figure className="cartel-qr principal">
                        <CodigoQR texto={URL_WHATSAPP} tamano={190} />
                        <figcaption><strong>WhatsApp</strong><span>{WHATSAPP_VISIBLE}</span></figcaption>
                    </figure>
                    <figure className="cartel-qr">
                        <CodigoQR texto={URL_TELEGRAM} tamano={130} />
                        <figcaption><strong>Telegram</strong><span>@{TELEGRAM_BOT}</span></figcaption>
                    </figure>
                    <figure className="cartel-qr">
                        <CodigoQR texto={urlChat} tamano={130} />
                        <figcaption><strong>Sin WhatsApp</strong><span>{window.location.host}/chat</span></figcaption>
                    </figure>
                </div>
                <p className="cartel-camara"><Icono nombre="mira" tamano={18} /> Abre la cámara del celular y apunta al código</p>

                <div className="cartel-nunca">
                    <strong>Recuerda: tu banco, Nequi, Daviplata y la Policía NUNCA te piden claves ni códigos por mensaje o llamada.</strong>
                    <span>Emergencia: <b>123</b> · Fiscalía: <b>122</b> · CAI Virtual: caivirtual.policia.gov.co</span>
                </div>

                <footer className="cartel-pie">
                    <span>Gratis · Anónimo: no guardamos tu número</span>
                    {lugar.trim() && <span className="cartel-lugar"><Icono nombre="pin" tamano={14} /> {lugar.trim()}</span>}
                </footer>
            </article>
        </div>
    )
}
