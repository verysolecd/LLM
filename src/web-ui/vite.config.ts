import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true,
        rewrite: (path) => path
      },
      '/temp_audio': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true
      },
      '/temp_upload': {
        target: 'http://127.0.0.1:5001',
        changeOrigin: true
      }
    }
  }
})
