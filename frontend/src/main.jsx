import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.jsx'
import { iniciarAlertas } from './services/alertas.js'
import 'leaflet/dist/leaflet.css'
import './styles.css'

// La consulta a Firestore arranca en paralelo al primer render, no al montar el panel
iniciarAlertas()

ReactDOM.createRoot(document.getElementById('root')).render(
    <React.StrictMode>
        <BrowserRouter>
            <App />
        </BrowserRouter>
    </React.StrictMode>,
)
