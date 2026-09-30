import axios from 'axios'

// 统一 API 客户端，所有业务接口挂 /api 前缀。
export const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 自动附带登录令牌。
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
