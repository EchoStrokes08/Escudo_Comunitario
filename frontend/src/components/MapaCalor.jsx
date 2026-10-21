import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, Circle, Popup, useMap } from 'react-leaflet'
import { CENTRO_BOSA } from '../data/barrios.js'
import { nivelRiesgo } from '../utils/riesgo.js'

/** Radio del punto de calor proporcional al nivel de riesgo (en metros). */
const radioPorRiesgo = (riesgo = 0) => 250 + (riesgo * 12)

/** Ajusta el zoom del mapa para encuadrar todos los reportes activos. */
function AjustarVista({ puntos }) {
    const map = useMap()

    useEffect(() => {
        if (puntos.length > 1) {
            const bounds = puntos.map(p => [p.lat, p.lng])
            map.fitBounds(bounds, { padding: [60, 60], maxZoom: 15 })
        } else if (puntos.length === 1) {
            map.setView([puntos[0].lat, puntos[0].lng], 15)
        }
    }, [puntos, map])

    return null
}

export default function MapaCalor({ reportes = [] }) {
    const puntos = useMemo(
        () => reportes.filter(r => typeof r.lat === 'number' && typeof r.lng === 'number'),
        [reportes]
    )

    return (
        <div className="mapa-envoltura">
            <MapContainer
                center={[CENTRO_BOSA.lat, CENTRO_BOSA.lng]}
                zoom={13}
                scrollWheelZoom={false}
                className="mapa"
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                <AjustarVista puntos={puntos} />

                {puntos.map(reporte => {
                    const { color, etiqueta } = nivelRiesgo(reporte.nivel_riesgo)
                    return (
                        <Circle
                            key={reporte.id}
                            center={[reporte.lat, reporte.lng]}
                            radius={radioPorRiesgo(reporte.nivel_riesgo)}
                            pathOptions={{
                                color,
                                fillColor: color,
                                fillOpacity: 0.35,
                                weight: 2,
                            }}
                        >
                            <Popup>
                                <strong>{etiqueta} riesgo: {reporte.nivel_riesgo}%</strong><br />
                                {reporte.barrio && <>Barrio: {reporte.barrio}<br /></>}
                                {(reporte.mensaje_original || '').slice(0, 90)}…
                            </Popup>
                        </Circle>
                    )
                })}
            </MapContainer>

            <div className="mapa-leyenda">
                <span><i style={{ background: '#0e7490' }} /> Riesgo bajo</span>
                <span><i style={{ background: '#9a6b00' }} /> Riesgo medio</span>
                <span><i style={{ background: '#c3381f' }} /> Riesgo alto</span>
            </div>
        </div>
    )
}
