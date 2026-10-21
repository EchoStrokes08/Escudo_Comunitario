import { lazy, Suspense } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Icono from './components/Icono.jsx'

// El formulario se descarga solo cuando se abre: el panel con el mapa arranca más ligero
const Reportar = lazy(() => import('./pages/Reportar.jsx'))

function App() {
    const ubicacion = useLocation()

    return (
        <div className="app">
            <div className="fondo-decorativo" aria-hidden="true" />

            <header className="navbar">
                <NavLink to="/" className="navbar-marca">
                    <span className="navbar-escudo"><Icono nombre="escudo" tamano={22} grosor={2} /></span>
                    <span>
                        <strong>Escudo Comunitario</strong>
                        <small>Prevención de fraude digital · Bosa</small>
                    </span>
                </NavLink>
                <nav>
                    <NavLink to="/" end className="nav-enlace">
                        <Icono nombre="mapa" tamano={16} /> <span>Panel</span>
                    </NavLink>
                    <NavLink to="/reportar" className="nav-enlace nav-cta">
                        <Icono nombre="bandera" tamano={16} /> <span>Reportar</span>
                    </NavLink>
                </nav>
            </header>

            {/* key: cada cambio de ruta re-dispara la animación de entrada */}
            <main className="contenido" key={ubicacion.pathname}>
                <Suspense fallback={<div className="cargando-pagina"><span className="spinner" /></div>}>
                    <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/reportar" element={<Reportar />} />
                        <Route path="*" element={<Dashboard />} />
                    </Routes>
                </Suspense>
            </main>

            <footer className="pie">
                <span><Icono nombre="escudo" tamano={14} /> Escudo Comunitario · Localidad 07 Bosa, Bogotá D.C.</span>
                <span>Cada reporte queda sellado con un certificado SHA-256.</span>
            </footer>
        </div>
    )
}

export default App
