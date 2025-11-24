import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBaseUrl = (env.VITE_API_BASE_URL || 'https://api.security.ait.dtu.dk').replace(/\/$/, '');

  return {
    plugins: [react()],
    server: {
      port: 3030,
      strictPort: true, // Force Vite to use port 3030 only, fail if busy
      open: true,
      proxy: {
        // Proxy API calls to avoid CORS issues
        '/api': {
          target: apiBaseUrl,
          changeOrigin: true,
          secure: true,
          rewrite: path => path.replace(/^\/api/, ''),
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request to the Target:', req.method, req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          }
        }
      }
    }
  };
});
