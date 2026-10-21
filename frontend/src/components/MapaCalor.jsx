import { useMemo } from 'react'
import { MapContainer, TileLayer, Circle, Polygon, Popup } from 'react-leaflet'
import { CENTRO_BOSA, MAX_BOUNDS, VERTICES_BOSA, dentroDeBosa } from '../data/bosaPolygon.js'
import { nivelRiesgo } from '../utils/riesgo.js'

/** Radio del punto de calor proporcional al nivel de riesgo (en metros). */
const radioPorRiesgo = (riesgo = 0) => 250 + (riesgo * 12)

export default function MapaCalor({ reportes = [] }) {
    // Solo se pintan reportes caídos estrictamente dentro del polígono de Bosa
    const puntos = useMemo(
        () => reportes.filter(r =>
            typeof r.lat === 'number' &&
            typeof r.lng === 'number' &&
            dentroDeBosa(r.lat, r.lng)
        ),
        [reportes]
    )

    return (
        <div className="mapa-envoltura">
            <MapContainer
                center={CENTRO_BOSA}
                zoom={13}
                minZoom={12}
                maxZoom={18}
                maxBounds={MAX_BOUNDS}
                maxBoundsViscosity={1.0}
                scrollWheelZoom={false}
                worldCopyJump={false}
                className="mapa"
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Frontera de la localidad de Bosa (tenue, aspecto profesional) */}
                <Polygon
                    positions={VERTICES_BOSA}
                    pathOptions={{
                        color: '#0e7490',
                        weight: 2,
                        opacity: 0.8,
                        fillColor: '#0e7490',
                        fillOpacity: 0.06,
                        dashArray: '6 4',
                    }}
                />

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
                                {(reporte.upz || reporte.barrio) && <>UPZ: {reporte.upz || reporte.barrio}<br /></>}
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
                <span className="texto-suave">📍 {puntos.length} de {reportes.length} reportes dentro de Bosa</span>
            </div>
        </div>
    )
}
