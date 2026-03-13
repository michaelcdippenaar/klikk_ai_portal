import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import fs from 'fs'
import path from 'path'

// Read and bump build number on every build (dev + production)
function bumpBuild(): { version: string; build: number } {
  const versionFile = path.resolve(__dirname, 'version.json')
  const data = JSON.parse(fs.readFileSync(versionFile, 'utf-8'))
  data.build++
  fs.writeFileSync(versionFile, JSON.stringify(data, null, 2) + '\n')
  return data
}

const versionInfo = bumpBuild()

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(versionInfo.version),
    __APP_BUILD__: JSON.stringify(versionInfo.build),
  },
  server: {
    port: 5173,
    proxy: {
      '/api/v1': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://localhost:8000',
        ws: true,
      },
      '/paw': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/cdn': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/prism': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/perspectives': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/css': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/images': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/wa-share': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/wa-save': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ui': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
