import axios from 'axios'

// 统一 API 客户端。后续业务接口统一挂 /api 前缀。
export const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})
