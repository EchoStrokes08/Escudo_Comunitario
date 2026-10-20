import { useEffect, useState } from 'react';
import { collection, onSnapshot, query, orderBy } from "firebase/firestore";
import { db } from '../services/firebase';

export default function Dashboard() {
    const [alertas, setAlertas] = useState([]);

    useEffect(() => {
        // Escucha la colección ordenando por los reportes más recientes
        const q = query(collection(db, "alertas_bosa"), orderBy("fecha", "desc"));

        const unsubscribe = onSnapshot(q, (snapshot) => {
            setAlertas(snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() })));
        });

        return () => unsubscribe();
    }, []);

    return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
            <h1>Inteligencia Territorial - Bosa</h1>
            <p>Reportes verificados en tiempo real</p>

            <div style={{ display: 'grid', gap: '1rem', marginTop: '2rem' }}>
                {alertas.map(alerta => (
                    <div key={alerta.id} style={{
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                        padding: '1rem',
                        borderLeft: alerta.nivel_riesgo >= 50 ? '4px solid #ef4444' : '4px solid #10b981'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <strong>Certificado: {alerta.certificado}</strong>
                            <span>Riesgo: {alerta.nivel_riesgo}%</span>
                        </div>
                        <p style={{ marginTop: '0.5rem', color: '#4b5563' }}>
                            {alerta.mensaje_original}
                        </p>
                        <small style={{ color: '#9ca3af' }}>
                            Fecha: {new Date(alerta.fecha).toLocaleString()}
                        </small>
                    </div>
                ))}
            </div>
        </div>
    );
}