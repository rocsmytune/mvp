import axios from 'axios'

// 数组参数序列化为重复键（types=a&types=b），供后端 FastAPI 的 list[str] 查询参数解析。
function paramsSerializer(params: Record<string, unknown>): string {
  const parts: string[] = []
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      for (const item of value) {
        parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(item))}`)
      }
    } else {
      parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    }
  }
  return parts.join('&')
}

// 统一 API 客户端，所有业务接口挂 /api 前缀。
export const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  paramsSerializer,
})

// 自动附带登录令牌。
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 从后端错误里提取可读文案（HTTPException 的 detail 为字符串，Pydantic 校验为列表）。
export function getErrorMessage(err: unknown, fallback = '操作失败'): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = (detail[0] as { msg?: string })?.msg
    if (msg) return msg
  }
  return fallback
}
