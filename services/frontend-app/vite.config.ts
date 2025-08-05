import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig, loadEnv } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file from current service directory
  const env = loadEnv(mode, __dirname, '')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: true, // Required for Docker
      port: 3000,
      watch: {
        usePolling: true,
      },
      // Proxy disabled - using direct axios calls with CORS
      // proxy: {
      //   '/api': {
      //     target: env.VITE_API_BASE_URL || 'http://localhost:3001',
      //     changeOrigin: true,
      //     secure: false,
      //   },
      //   '/auth': {
      //     target: env.VITE_API_BASE_URL || 'http://localhost:3001',
      //     changeOrigin: true,
      //     secure: false,
      //   },
      // },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            router: ['react-router-dom'],
            ui: ['framer-motion', 'lucide-react'],
          },
        },
      },
    },
  }
})
