import { useEffect, useState } from 'react'
import QRCode from 'qrcode'

/** QR que lleva a la página pública de verificación del certificado. */
export default function CodigoQR({ texto, tamano = 148, className = '' }) {
    const [src, setSrc] = useState(null)

    useEffect(() => {
        let vigente = true
        QRCode.toDataURL(texto, { margin: 1, width: tamano * 2, errorCorrectionLevel: 'M', color: { dark: '#070c17', light: '#ffffff' } })
            .then(url => vigente && setSrc(url))
            .catch(() => vigente && setSrc(null))
        return () => { vigente = false }
    }, [texto, tamano])

    if (!src) return <div className={`qr qr-vacio ${className}`} style={{ width: tamano, height: tamano }} />
    return <img className={`qr ${className}`} src={src} width={tamano} height={tamano} alt="Código QR para verificar el certificado" />
}
