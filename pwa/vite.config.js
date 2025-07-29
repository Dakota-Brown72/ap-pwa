import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(), 
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'AnchorPoint',
        short_name: 'APS',
        description: 'A central hub for your home or business systems',
        theme_color: '#E8E4DD',
        icons:[
          {
            src: '/icons/icon-192x192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512x512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512x512-maskable.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  resolve: {
  alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0', // Allow access from other devices on the network
    port: 5173,
    strictPort: true,
    https: false, // Explicitly disable HTTPS in dev mode
    allowedHosts: [
      'localhost',
      '127.0.0.1',
      'browns-aps.tail3174d7.ts.net',
      'dakota.anchorpointsystems.com',
    ],
    proxy: {
      '/api': {
        target: 'http://pwa-backend:5003',
        changeOrigin: true,
        secure: false,
        ws: false,
      },
    },
  }
})

