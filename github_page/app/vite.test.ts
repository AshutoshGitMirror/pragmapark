import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', sourcemap: false },
  server: { port: 5180,
    proxy: { '/api': { target: 'https://pragma-4szs.onrender.com', changeOrigin: true, secure: false, timeout: 600000 } }
  },
})
