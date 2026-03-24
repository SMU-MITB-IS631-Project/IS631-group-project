import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const rawApiProxyTarget = process.env.VITE_API_PROXY_TARGET
const rawApiBaseUrl = process.env.VITE_API_BASE_URL

if (rawApiProxyTarget !== undefined && rawApiProxyTarget.trim() === '') {
  throw new Error('VITE_API_PROXY_TARGET is set but empty. Remove it or set a valid URL.')
}

const apiProxyTarget =
  (rawApiProxyTarget && rawApiProxyTarget.trim()) ||
  (rawApiBaseUrl && rawApiBaseUrl.trim()) ||
  'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})
