import { useEffect, useState } from 'react';
import { collection, onSnapshot, query, orderBy } from "firebase/firestore";
import { db } from '../services/firebase';

export default function Dashboard() {
    const [alertas, setAlertas] = useState([]);

    useEffect(() => {
        const q = query(collection(db, "alertas_bosa"), orderBy("fecha", "desc"));

        const unsubscribe = onSnapshot(q, (snapshot) => {
            setAlertas(snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() })));
        });

        return () => unsubscribe();
    }, []);

    return (
        <div style={{ padding: '2rem', fontFamily: 'sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
            <h1 style={{ fontSize: '2rem', color: '#111827' }}>Escudo Comunitario Bosa</h1>
            <p style={{ color: '#6b7280', marginBottom: '2rem' }}>Panel de Inteligencia Territorial en Tiempo Real</p>

            <div style={{ display: 'grid', gap: '1rem' }}>
                {alertas.length === 0 ? (
                    <p style={{ color: '#9ca3af' }}>Esperando reportes...</p>
                ) : (
                    alertas.map(alerta => (
                        <div key={alerta.id} style={{
                            border: '1px solid #e5e7eb',
                            borderRadius: '8px',
                            padding: '1.5rem',
                            background: '#ffffff',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                            borderLeft: alerta.nivel_riesgo >= 50 ? '5px solid #ef4444' : '5px solid #10b981'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <strong style={{ fontFamily: 'monospace', color: '#374151' }}>
                                    Certificado: {alerta.certificado}
                                </strong>
                                <span style={{
                                    background: alerta.nivel_riesgo >= 50 ? '#fee2e2' : '#d1fae5',
                                    color: alerta.nivel_riesgo >= 50 ? '#991b1b' : '#065f46',
                                    padding: '4px 12px',
                                    borderRadius: '999px',
                                    fontWeight: 'bold',
                                    fontSize: '0.875rem'
                                }}>
                                    Riesgo: {alerta.nivel_riesgo}%
                                </span>
                            </div>
                            <p style={{ color: '#4b5563', fontSize: '1.1rem', margin: '0 0 1rem 0' }}>
                                "{alerta.mensaje_original}"
                            </p>
                            <div style={{ color: '#9ca3af', fontSize: '0.875rem' }}>
                                Registrado: {new Date(alerta.fecha).toLocaleString('es-CO')}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}