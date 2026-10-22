import { memo, useEffect, useMemo, useRef } from 'react'
import { MapContainer, TileLayer, Circle, Polygon, Popup } from 'react-leaflet'
import { CENTRO_BOSA, MAX_BOUNDS, VERTICES_BOSA } from '../data/bosaPolygon.js'
import { nivelRiesgo, TONOS } from '../utils/riesgo.js'
import Icono from './Icono.jsx'

/** Radio del punto de calor proporcional al nivel de riesgo (en metros): de 100 m (0%) a 300 m (100%). */
const radioPorRiesgo = (riesgo = 0) => 100 + (riesgo * 2)

// Los reportes llegan normalizados desde services/alertas.js: siempre con lat/lng dentro de Bosa
export const tieneCoordenadas = (r) => typeof r.lat === 'number' && typeof r.lng === 'number'

const ESTILO_FRONTERA = {
    color: TONOS.bajo,
    weight: 2,
    opacity: 0.85,
    fillColor: TONOS.bajo,
    fillOpacity: 0.05,
    dashArray: '6 6',
}

/** Capa de puntos memorizada: no se repinta al cambiar filtros o búsqueda del panel. */
const PuntosCalor = memo(function PuntosCalor({ puntos, seleccionadoId, onSeleccionar, circulos }) {
    return puntos.map(reporte => {
        const { tono, etiqueta, id } = nivelRiesgo(reporte.nivel_riesgo)
        const activo = reporte.id === seleccionadoId
        const texto = reporte.mensaje_anonimizado || ''
        return (
            <Circle
                key={reporte.id}
                ref={ref => { if (ref) circulos.current[reporte.id] = ref }}
                center={[reporte.lat, reporte.lng]}
                radius={radioPorRiesgo(reporte.nivel_riesgo)}
                pathOptions={{
                    color: tono,
                    fillColor: tono,
                    fillOpacity: activo ? 0.55 : 0.28,
                    weight: activo ? 3 : 1.5,
                }}
                eventHandlers={{ click: () => onSeleccionar?.(reporte.id) }}
            >
                <Popup>
                    <div className="popup">
                        <span className={`popup-nivel texto-${id}`}>
                            Riesgo {etiqueta.toLowerCase()} · {reporte.nivel_riesgo}%
                        </span>
                        <span className="popup-upz">
                            UPZ {reporte.upz || 'Bosa'}{reporte.aproximada ? ' · ubicación aproximada' : ''}
                        </span>
                        <p>{texto.slice(0, 110)}{texto.length > 110 ? '…' : ''}</p>
                    </div>
                </Popup>
            </Circle>
        )
    })
})

export default function MapaCalor({ reportes = [], cargando = false, seleccionadoId = null, onSeleccionar }) {
    const mapa = useRef(null)
    const circulos = useRef({})

    const puntos = useMemo(() => reportes.filter(tieneCoordenadas), [reportes])
    const exactos = useMemo(() => puntos.filter(p => !p.aproximada).length, [puntos])

    // Al seleccionar un reporte desde la lista, el mapa vuela hasta él y abre su ficha
    useEffect(() => {
        const destino = puntos.find(p => p.id === seleccionadoId)
        const instancia = mapa.current
        if (!destino || !instancia) return
        instancia.flyTo([destino.lat, destino.lng], 16, { duration: 1.1 })
        instancia.once('moveend', () => circulos.current[destino.id]?.openPopup())
    }, [seleccionadoId, puntos])

    const recentrar = () => {
        mapa.current?.closePopup()
        mapa.current?.flyTo(CENTRO_BOSA, 13, { duration: 0.9 })
    }

    return (
        <div className="mapa-envoltura">
            <MapContainer
                ref={mapa}
                center={CENTRO_BOSA}
                zoom={13}
                minZoom={12}
                maxZoom={18}
                maxBounds={MAX_BOUNDS}
                maxBoundsViscosity={1.0}
                scrollWheelZoom={false}
                worldCopyJump={false}
                preferCanvas
                className="mapa"
            >
                {/* OSM estándar (sin API key) oscurecido por CSS: .capa-oscura */}
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                    className="capa-oscura"
                    keepBuffer={4}
                    updateWhenZooming={false}
                />

                <Polygon positions={VERTICES_BOSA} interactive={false} pathOptions={ESTILO_FRONTERA} />

                <PuntosCalor
                    puntos={puntos}
                    seleccionadoId={seleccionadoId}
                    onSeleccionar={onSeleccionar}
                    circulos={circulos}
                />
            </MapContainer>

            <div className="mapa-leyenda">
                <span><i className="punto-leyenda fondo-alto" /> Alto</span>
                <span><i className="punto-leyenda fondo-medio" /> Medio</span>
                <span><i className="punto-leyenda fondo-bajo" /> Bajo</span>
            </div>

            <button type="button" className="mapa-recentrar" onClick={recentrar} title="Ver toda la localidad">
                <Icono nombre="mira" tamano={16} /> Bosa completa
            </button>

            <div className="mapa-contador">
                {cargando
                    ? <><span className="spinner spinner-pequeno" /> Cargando reportes…</>
                    : <><strong>{puntos.length}</strong> reportes en el mapa · {exactos} con GPS exacto</>}
            </div>
        </div>
    )
}
