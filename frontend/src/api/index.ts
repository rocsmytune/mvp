import { api } from './client'
import type { Overview } from './types'

// 机房总览：一次拉取机房、机柜、设备统计与已上架/待整理数量。
export async function fetchOverview(): Promise<Overview> {
  const res = await api.get<Overview>('/overview')
  return res.data
}
