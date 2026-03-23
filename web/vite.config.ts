import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/chat':     { target: 'http://localhost:8001', rewrite: p => p.replace(/^\/api\/chat/, '') },
      '/api/memory':   { target: 'http://localhost:8002', rewrite: p => p.replace(/^\/api\/memory/, '') },
      '/api/persona':  { target: 'http://localhost:8003', rewrite: p => p.replace(/^\/api\/persona/, '') },
      '/api/payment':  { target: 'http://localhost:8004', rewrite: p => p.replace(/^\/api\/payment/, '') },
      '/api/training': { target: 'http://localhost:8005', rewrite: p => p.replace(/^\/api\/training/, '') },
    }
  }
})
