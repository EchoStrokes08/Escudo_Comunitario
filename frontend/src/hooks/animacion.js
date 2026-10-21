import { useEffect, useRef, useState } from 'react'

const sinMovimiento = () =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

/** Anima un número desde su valor anterior hasta `objetivo`. */
export function useContador(objetivo, duracion = 900) {
    const [valor, setValor] = useState(0)
    const anterior = useRef(0)

    useEffect(() => {
        const inicio = anterior.current
        if (sinMovimiento() || inicio === objetivo) {
            anterior.current = objetivo
            setValor(objetivo)
            return
        }
        let marco
        const t0 = performance.now()
        const paso = (t) => {
            const p = Math.min((t - t0) / duracion, 1)
            const suavizado = 1 - Math.pow(1 - p, 3)
            setValor(Math.round(inicio + (objetivo - inicio) * suavizado))
            if (p < 1) marco = requestAnimationFrame(paso)
            else anterior.current = objetivo
        }
        marco = requestAnimationFrame(paso)
        return () => {
            cancelAnimationFrame(marco)
            anterior.current = objetivo
        }
    }, [objetivo, duracion])

    return valor
}

/** Fuerza un re-render periódico (para tiempos relativos). */
export function useAhora(intervalo = 30_000) {
    const [ahora, setAhora] = useState(Date.now())
    useEffect(() => {
        const id = setInterval(() => setAhora(Date.now()), intervalo)
        return () => clearInterval(id)
    }, [intervalo])
    return ahora
}
