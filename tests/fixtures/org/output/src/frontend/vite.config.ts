import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In Docker compose the API is reachable at http://org-api:8000;
// locally it's at http://localhost:8000. VITE_API_HOST lets compose override it.
const apiHost = process.env.VITE_API_HOST ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  build: { outDir: '../../public', emptyOutDir: true },
  server: {
    proxy: {
      '/agents':    apiHost,
      '/workflows': apiHost,
      '/api': apiHost,
    }
  }
})
