import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发服务器把 /api 与 /health 代理到后端；后端地址可用环境变量覆盖。
const backend = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
      '/health': { target: backend, changeOrigin: true },
    },
  },
})
