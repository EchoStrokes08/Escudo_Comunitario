/**
 * Unidades de Planeamiento Zonal (UPZ) de la Localidad de Bosa (Bogotá D.C. - Localidad 07).
 *
 * Las 5 UPZ oficiales de Bosa son:
 *  - Apogeo (UPZ 49)
 *  - Bosa Occidental (UPZ 84)
 *  - Bosa Central (UPZ 85)
 *  - El Porvenir (UPZ 86)
 *  - Tintal Sur (UPZ 87)
 */

export const UPZ_BOSA = [
    {
        id: '85',
        codigo: 'UPZ 85',
        nombre: 'Bosa Central',
        sectores: 'Bosa Centro, El Pinar, San Pablo, La Estación, Carbonell, Bosa Nova',
        lat: 4.6060,
        lng: -74.1860,
    },
    {
        id: '86',
        codigo: 'UPZ 86',
        nombre: 'El Porvenir',
        sectores: 'El Porvenir, El Recreo, Campo Verde, Santa Fe Bosa',
        lat: 4.6370,
        lng: -74.2060,
    },
    {
        id: '84',
        codigo: 'UPZ 84',
        nombre: 'Bosa Occidental',
        sectores: 'San Bernardino, Potrerito, Las Margaritas, Villas del Progreso, San José',
        lat: 4.6220,
        lng: -74.2120,
    },
    {
        id: '87',
        codigo: 'UPZ 87',
        nombre: 'Tintal Sur',
        sectores: 'Tintalito, Caldas, Ciudad Hunza, Brasilia, Chicalá',
        lat: 4.6240,
        lng: -74.1900,
    },
    {
        id: '49',
        codigo: 'UPZ 49',
        nombre: 'Apogeo',
        sectores: 'Olarte, Nuevo Chile, Villa del Río, Portal del Sur, Terminal del Sur',
        lat: 4.6010,
        lng: -74.1640,
    },
]

/** Encuentra la UPZ cuyo centro geográfico está más próximo a las coordenadas dadas */
export function obtenerUpzMasCercana(lat, lng) {
    if (lat == null || lng == null) return UPZ_BOSA[0]
    let mejor = UPZ_BOSA[0]
    let menorDistancia = Infinity
    for (const upz of UPZ_BOSA) {
        const d = Math.hypot(lat - upz.lat, lng - upz.lng)
        if (d < menorDistancia) {
            menorDistancia = d
            mejor = upz
        }
    }
    return mejor
}

/** Alias para compatibilidad con código anterior */
export const BARRIOS_BOSA = UPZ_BOSA
