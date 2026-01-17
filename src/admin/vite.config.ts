import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://192.168.50.13:8008',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://192.168.50.13:8008',
        ws: true,
      },
    },
  },
})
