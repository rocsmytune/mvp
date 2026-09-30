// 与后端 Pydantic 模型对齐的类型定义。

export interface UserInfo {
  employee_no: string
  name: string
  role: string
}

export interface Room {
  id: number
  city: string | null
  code: string
  zone: string | null
  remark: string | null
}

export interface CabinetSummary {
  id: number
  room_id: number
  room_code: string | null
  name: string
  owner_id: number | null
  owner_name: string | null
  total_u: number
  device_count: number
  used_u: number
}

export interface Overview {
  placed_count: number
  pool_count: number
  rooms: Room[]
  cabinets: CabinetSummary[]
}
