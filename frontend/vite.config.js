import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    build: {
        rollupOptions: {
            output: {
                // Bloques separados: se descargan en paralelo y se cachean entre despliegues
                manualChunks: {
                    react: ['react', 'react-dom', 'react-router-dom'],
                    mapa: ['leaflet', 'react-leaflet'],
                    firebase: ['firebase/app', 'firebase/firestore'],
                },
            },
        },
    },
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
})
