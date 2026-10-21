const TRAZOS = {
    escudo: <><path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6l8-3z" /><path d="M9 12l2 2 4-4" /></>,
    bandera: <><path d="M5 21V4" /><path d="M5 4h12l-2.5 4L17 12H5" /></>,
    pin: <><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z" /><circle cx="12" cy="10" r="2.5" /></>,
    subir: <><path d="M12 15V4" /><path d="M7 9l5-5 5 5" /><path d="M4 15v4a1 1 0 001 1h14a1 1 0 001-1v-4" /></>,
    archivo: <><path d="M14 3H6a1 1 0 00-1 1v16a1 1 0 001 1h12a1 1 0 001-1V8z" /><path d="M14 3v5h5" /><path d="M9 13h6M9 17h4" /></>,
    cerrar: <path d="M6 6l12 12M18 6L6 18" />,
    buscar: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
    reloj: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    mensaje: <path d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z" />,
    clip: <path d="M20 11.5l-8.2 8.2a5 5 0 01-7-7L13.6 4a3.4 3.4 0 014.8 4.8l-8.6 8.6a1.7 1.7 0 01-2.4-2.4L15 7.4" />,
    copiar: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a1 1 0 011-1h10" /></>,
    check: <path d="M5 12.5l4.5 4.5L19 7" />,
    recargar: <><path d="M20 12a8 8 0 11-2.4-5.7" /><path d="M20 4v5h-5" /></>,
    mira: <><circle cx="12" cy="12" r="7" /><circle cx="12" cy="12" r="2" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
    alerta: <><path d="M12 3.5l9 16H3z" /><path d="M12 10v4M12 17h.01" /></>,
    flecha: <path d="M5 12h14M13 6l6 6-6 6" />,
    portapapeles: <><rect x="6" y="4.5" width="12" height="16" rx="2" /><path d="M9.5 3h5v3h-5z" /></>,
    pulso: <path d="M3 12h4l3-7 4 14 3-7h4" />,
    mapa: <><path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" /><path d="M9 4v14M15 6v14" /></>,
    hash: <path d="M5 9h14M5 15h14M10 3L8 21M16 3l-2 18" />,
    capas: <><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" /></>,
    imagen: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="2" /><path d="M21 16l-5-5-9 9" /></>,
    chispa: <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6" />,
}

export default function Icono({ nombre, tamano = 18, grosor = 1.8, className = '', ...resto }) {
    return (
        <svg
            width={tamano}
            height={tamano}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={grosor}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={`icono ${className}`}
            {...resto}
        >
            {TRAZOS[nombre]}
        </svg>
    )
}
