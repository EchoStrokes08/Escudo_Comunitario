/** Ciclo de vida de un caso (igual a ESTADOS_CASO en backend/app/services/registro.py). */
export const ESTADOS_CASO = {
    registrado: { etiqueta: 'Reporte registrado', icono: 'archivo' },
    en_revision: { etiqueta: 'En revisión', icono: 'buscar' },
    remitido: { etiqueta: 'Remitido a Policía / Fiscalía', icono: 'flecha' },
    en_investigacion: { etiqueta: 'En investigación', icono: 'mira' },
    cerrado: { etiqueta: 'Caso cerrado', icono: 'check' },
}

export const ORDEN_ESTADOS = Object.keys(ESTADOS_CASO)

export const etiquetaEstado = (estado) => ESTADOS_CASO[estado]?.etiqueta || 'Reporte registrado'
