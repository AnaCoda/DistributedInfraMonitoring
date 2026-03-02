import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      // Proxy API calls to the capital server
      '/api': 'http://localhost:5000',
    },
  },
})
