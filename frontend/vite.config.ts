import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 12001,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:12000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:12000',
        ws: true,
      },
    },
  },
})
