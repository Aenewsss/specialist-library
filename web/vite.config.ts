import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// A API (FastAPI) roda à parte; no dev, /api é repassado para ela, sem precisar de CORS.
const apiUrl = process.env.API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: apiUrl, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
})
