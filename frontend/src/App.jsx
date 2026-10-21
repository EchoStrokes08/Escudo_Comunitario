import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import Reportar from './pages/Reportar.jsx'

function App() {
    return (
        <div className="app">
            <header className="navbar">
                <div className="navbar-marca">
                    <span className="navbar-escudo">🛡️</span>
                    <div>
                        <h1>Escudo Comunitario</h1>
                        <p>Prevención de fraude digital · Localidad de Bosa</p>
                    </div>
                </div>
                <nav>
                    <NavLink to="/" end>Panel Territorial</NavLink>
                    <NavLink to="/reportar" className="nav-cta">🚩 Reportar</NavLink>
                </nav>
            </header>

            <main className="contenido">
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/reportar" element={<Reportar />} />
                    <Route path="*" element={<Dashboard />} />
                </Routes>
            </main>
        </div>
    )
}

export default App
