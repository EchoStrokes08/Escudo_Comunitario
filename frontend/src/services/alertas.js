/**
 * Almacén único de reportes (colección panel_publico: versión anonimizada).
 * Los casos completos (alertas_bosa) solo los ve el backend y la vista de autoridades.
 *
 * - Una sola suscripción onSnapshot para toda la app: cambiar de página no vuelve a consultar.
 * - Se inicia en main.jsx, en paralelo al primer render, para que los datos lleguen antes.
 * - Procesa solo los documentos que cambian (docChanges) y conserva la identidad de los demás.
 * - Normaliza documentos antiguos: coordenadas en texto o nulas, fechas como Timestamp, etc.
 */
import { useSyncExternalStore } from 'react'
import { collection, limit, onSnapshot, orderBy, query } from 'firebase/firestore'
import { db } from './firebase'
import { CENTRO_BOSA, dentroDeBosa } from '../data/bosaPolygon.js'
import { UPZ_BOSA } from '../data/upz.js'
import { nivelRiesgo } from '../utils/riesgo.js'

export const COLECCION = 'panel_publico'
export const COLECCION_ALERTAS = 'alertas_comunitarias'
const LIMITE = 500
const DURACION_NUEVO_MS = 6000

// Mismo radio de dispersión que backend/app/services/geolocalizacion.py (~380 m)
const RADIO_JITTER = 0.0035

let estado = {
    alertas: [],
    cargando: true,
    error: null,
    desdeCache: true,
    actualizado: null,
    nuevos: new Set(),
}

const oyentes = new Set()
const porId = new Map()
let cancelar = null
let sincronizadoConServidor = false

function emitir(parcial) {
    estado = { ...estado, ...parcial }
    oyentes.forEach(oyente => oyente())
}

/** Hash FNV-1a → fracción 0..1, determinística por documento. */
function fraccion(semilla) {
    let h = 0x811c9dc5
    for (let i = 0; i < semilla.length; i++) {
        h ^= semilla.charCodeAt(i)
        h = Math.imul(h, 0x01000193)
    }
    return (h >>> 0) / 0xffffffff
}

const aNumero = (valor) => {
    if (valor === null || valor === undefined || valor === '') return null
    const n = typeof valor === 'number' ? valor : Number(valor)
    return Number.isFinite(n) ? n : null
}

function aFechaIso(valor) {
    if (!valor) return null
    if (typeof valor.toDate === 'function') return valor.toDate().toISOString()
    if (typeof valor.seconds === 'number') return new Date(valor.seconds * 1000).toISOString()
    const fecha = new Date(valor)
    return Number.isNaN(fecha.getTime()) ? null : fecha.toISOString()
}

/** Coordenadas aproximadas (centro de la UPZ + dispersión) para reportes sin GPS válido. */
function ubicacionPorUpz(nombre, semilla) {
    const upz = UPZ_BOSA.find(u => u.nombre.toLowerCase() === (nombre || '').trim().toLowerCase())
    const base = upz ? [upz.lat, upz.lng] : CENTRO_BOSA
    for (let intento = 0; intento < 12; intento++) {
        const lat = base[0] + (fraccion(`${semilla}:${intento}:0`) * 2 - 1) * RADIO_JITTER
        const lng = base[1] + (fraccion(`${semilla}:${intento}:1`) * 2 - 1) * RADIO_JITTER
        if (dentroDeBosa(lat, lng)) return [lat, lng]
    }
    return base
}

function normalizar(id, datos) {
    const upz = datos.upz || datos.barrio || null
    let lat = aNumero(datos.lat ?? datos.latitud ?? datos.ubicacion?.latitude)
    let lng = aNumero(datos.lng ?? datos.longitud ?? datos.ubicacion?.longitude)
    let aproximada = false

    if (lat === null || lng === null || !dentroDeBosa(lat, lng)) {
        if (upz) {
            ;[lat, lng] = ubicacionPorUpz(upz, id)
            aproximada = true
        } else {
            // Reporte de WhatsApp que aún no indica su UPZ: cuenta en las estadísticas, no en el mapa
            lat = null
            lng = null
        }
    }

    const riesgo = Math.max(0, Math.min(100, Math.round(aNumero(datos.nivel_riesgo) ?? 0)))

    return {
        ...datos,
        id,
        upz,
        lat,
        lng,
        aproximada,
        nivel_riesgo: riesgo,
        nivel: nivelRiesgo(riesgo).id,
        fecha: aFechaIso(datos.fecha),
        mensaje_anonimizado: datos.mensaje_anonimizado || '',
        confianza: Math.round(aNumero(datos.confianza) ?? 0),
        tipo_fraude: datos.tipo_fraude || 'otro',
        flags: Array.isArray(datos.flags) ? datos.flags : [],
        hallazgos: Array.isArray(datos.hallazgos) ? datos.hallazgos : [],
        indicadores: Array.isArray(datos.indicadores) ? datos.indicadores : [],
    }
}

function marcarNuevos(ids) {
    if (!ids.length) return
    emitir({ nuevos: new Set([...estado.nuevos, ...ids]) })
    setTimeout(() => {
        const resto = new Set(estado.nuevos)
        ids.forEach(id => resto.delete(id))
        emitir({ nuevos: resto })
    }, DURACION_NUEVO_MS)
}

export function iniciarAlertas() {
    if (cancelar) return

    const consulta = query(collection(db, COLECCION), orderBy('fecha', 'desc'), limit(LIMITE))

    cancelar = onSnapshot(consulta, { includeMetadataChanges: true }, (snapshot) => {
        const cambios = snapshot.docChanges()
        const agregados = []

        for (const cambio of cambios) {
            const { doc, type } = cambio
            if (type === 'removed') {
                porId.delete(doc.id)
            } else {
                porId.set(doc.id, normalizar(doc.id, doc.data()))
                if (type === 'added') agregados.push(doc.id)
            }
        }

        // Solo se resaltan como "nuevos" los que llegan en vivo, no la sincronización inicial
        if (sincronizadoConServidor) marcarNuevos(agregados)
        if (!snapshot.metadata.fromCache) sincronizadoConServidor = true

        emitir({
            alertas: cambios.length ? snapshot.docs.map(d => porId.get(d.id)) : estado.alertas,
            // Con caché vacía el primer snapshot llega sin datos: seguimos "cargando" hasta el servidor
            cargando: snapshot.metadata.fromCache && snapshot.empty && !sincronizadoConServidor,
            desdeCache: snapshot.metadata.fromCache,
            actualizado: Date.now(),
            error: null,
        })
    }, (error) => {
        console.error('[Firestore] Error al escuchar reportes:', error)
        cancelar = null
        emitir({ cargando: false, error })
    })
}

function suscribir(oyente) {
    oyentes.add(oyente)
    iniciarAlertas()
    return () => oyentes.delete(oyente)
}

const leer = () => estado

/** Hook: reportes normalizados y en tiempo real, compartidos por toda la app. */
export function useAlertas() {
    return useSyncExternalStore(suscribir, leer)
}


/* ---------- Alertas comunitarias (brotes por UPZ) ---------- */

let estadoAlertasComunidad = []
const oyentesComunidad = new Set()
let cancelarComunidad = null

function suscribirComunidad(oyente) {
    oyentesComunidad.add(oyente)
    if (!cancelarComunidad) {
        const consulta = query(collection(db, COLECCION_ALERTAS), orderBy('fecha', 'desc'), limit(6))
        cancelarComunidad = onSnapshot(consulta, (snapshot) => {
            estadoAlertasComunidad = snapshot.docs.map(d => ({ id: d.id, ...d.data() }))
            oyentesComunidad.forEach(o => o())
        }, (error) => console.error('[Firestore] Alertas comunitarias:', error))
    }
    return () => oyentesComunidad.delete(oyente)
}

/** Hook: brotes de fraude detectados por el backend en las últimas horas. */
export function useAlertasComunitarias() {
    return useSyncExternalStore(suscribirComunidad, () => estadoAlertasComunidad)
}
