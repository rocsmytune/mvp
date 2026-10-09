import { api } from './client'
import type {
  Asset,
  AssetCreatePayload,
  AssetUpdatePayload,
  Cabinet,
  CabinetCreatePayload,
  CabinetUpdatePayload,
  ChangeLogEntry,
  Component,
  ComponentCreatePayload,
  ComponentUpdatePayload,
  Dictionary,
  DictionaryCreatePayload,
  DictionaryUpdatePayload,
  DictionaryUsage,
  ExportSnapshot,
  Facets,
  ImportBatch,
  ImportConfirmResponse,
  ImportRow,
  ImportUploadResponse,
  OwnerOption,
  Overview,
  Room,
  RoomCreatePayload,
  RoomUpdatePayload,
  SearchResult,
  UserAdmin,
  UserCreatePayload,
  UserUpdatePayload,
} from './types'

// 机房总览：一次拉取机房、机柜、设备统计与已上架/待整理数量。
export async function fetchOverview(): Promise<Overview> {
  const res = await api.get<Overview>('/overview')
  return res.data
}

// 某机柜下的设备列表（详情抽屉用）。
export async function fetchAssets(cabinetId: number): Promise<Asset[]> {
  const res = await api.get<{ total: number; items: Asset[] }>('/assets', {
    params: { cabinet_id: cabinetId, limit: 200 },
  })
  return res.data.items
}

// 某设备下的部件列表（详情抽屉用）。
export async function fetchComponents(assetId: number): Promise<Component[]> {
  const res = await api.get<{ total: number; items: Component[] }>('/components', {
    params: { asset_id: assetId, limit: 500 },
  })
  return res.data.items
}

// 设备列表页：服务端分页 + 过滤（多值列筛选）。
export async function fetchAssetPage(params?: {
  q?: string
  types?: string[]
  statuses?: string[]
  models?: string[]
  sns?: string[]
  ip_inbands?: string[]
  bmc_ips?: string[]
  room_codes?: string[]
  cabinet_names?: string[]
  remarks?: string[]
  skip?: number
  limit?: number
}): Promise<{ total: number; items: Asset[] }> {
  const res = await api.get<{ total: number; items: Asset[] }>('/assets', { params })
  return res.data
}

// 物料列表页：服务端分页 + 过滤（多值列筛选）。
export async function fetchComponentPage(params?: {
  categories?: string[]
  sns?: string[]
  material_codes?: string[]
  holder_names?: string[]
  room_codes?: string[]
  cabinet_names?: string[]
  remarks?: string[]
  skip?: number
  limit?: number
}): Promise<{ total: number; items: Component[] }> {
  const res = await api.get<{ total: number; items: Component[] }>('/components', { params })
  return res.data
}

// 设备列筛选 facet：各列去重值 + 计数（表头漏斗用）。
export async function fetchAssetFacets(): Promise<Facets> {
  const res = await api.get<Facets>('/assets/facets')
  return res.data
}

// 物料列筛选 facet：各列去重值 + 计数（表头漏斗用）。
export async function fetchComponentFacets(): Promise<Facets> {
  const res = await api.get<Facets>('/components/facets')
  return res.data
}

// 某设备的变更日志（按时间倒序）。
export async function fetchAssetChangelogs(assetId: number): Promise<ChangeLogEntry[]> {
  const res = await api.get<ChangeLogEntry[]>(`/assets/${assetId}/changelogs`)
  return res.data
}

// 全局搜索：整机SN / 部件SN / 带内IP / 带外IP / 资产编号。
export async function searchGlobal(q: string): Promise<SearchResult[]> {
  const res = await api.get<SearchResult[]>('/search', { params: { q } })
  return res.data
}

// ---------- 机柜管理（管理员） ----------

export async function fetchRooms(q?: string): Promise<Room[]> {
  const res = await api.get<{ total: number; items: Room[] }>('/rooms', { params: { q } })
  return res.data.items
}

export async function createRoom(data: RoomCreatePayload): Promise<Room> {
  const res = await api.post<Room>('/rooms', data)
  return res.data
}

export async function updateRoom(id: number, data: RoomUpdatePayload): Promise<Room> {
  const res = await api.patch<Room>(`/rooms/${id}`, data)
  return res.data
}

export async function deleteRoom(id: number): Promise<void> {
  await api.delete(`/rooms/${id}`)
}

export async function fetchCabinets(params?: {
  room_id?: number
  owner_id?: number
}): Promise<Cabinet[]> {
  const res = await api.get<{ total: number; items: Cabinet[] }>('/cabinets', { params })
  return res.data.items
}

export async function createCabinet(data: CabinetCreatePayload): Promise<Cabinet> {
  const res = await api.post<Cabinet>('/cabinets', data)
  return res.data
}

export async function updateCabinet(id: number, data: CabinetUpdatePayload): Promise<Cabinet> {
  const res = await api.patch<Cabinet>(`/cabinets/${id}`, data)
  return res.data
}

export async function deleteCabinet(id: number): Promise<void> {
  await api.delete(`/cabinets/${id}`)
}

export async function assignOwner(
  cabinetIds: number[],
  ownerId: number | null,
): Promise<{ updated: number }> {
  const res = await api.post<{ updated: number }>('/cabinets/assign-owner', {
    cabinet_ids: cabinetIds,
    owner_id: ownerId,
  })
  return res.data
}

export async function fetchCabinetOwners(): Promise<OwnerOption[]> {
  const res = await api.get<OwnerOption[]>('/users/cabinet-owners')
  return res.data
}

// ---------- 用户管理（仅系统管理员） ----------

export async function fetchUsers(params?: {
  q?: string
  role?: string
}): Promise<{ total: number; items: UserAdmin[] }> {
  const res = await api.get<{ total: number; items: UserAdmin[] }>('/users', { params })
  return res.data
}

export async function createUser(data: UserCreatePayload): Promise<UserAdmin> {
  const res = await api.post<UserAdmin>('/users', data)
  return res.data
}

export async function updateUser(id: number, data: UserUpdatePayload): Promise<UserAdmin> {
  const res = await api.patch<UserAdmin>(`/users/${id}`, data)
  return res.data
}

// ---------- 字典管理 ----------

export async function fetchDictionaries(kind?: string): Promise<Dictionary[]> {
  const res = await api.get<{ total: number; items: Dictionary[] }>('/dictionaries', {
    params: { kind },
  })
  return res.data.items
}

export async function createDictionary(data: DictionaryCreatePayload): Promise<Dictionary> {
  const res = await api.post<Dictionary>('/dictionaries', data)
  return res.data
}

export async function updateDictionary(
  id: number,
  data: DictionaryUpdatePayload,
): Promise<Dictionary> {
  const res = await api.patch<Dictionary>(`/dictionaries/${id}`, data)
  return res.data
}

export async function deleteDictionary(id: number): Promise<void> {
  await api.delete(`/dictionaries/${id}`)
}

export async function fetchDictionaryUsage(id: number): Promise<DictionaryUsage[]> {
  const res = await api.get<DictionaryUsage[]>(`/dictionaries/${id}/usage`)
  return res.data
}

// ---------- 编辑入口：资产/部件写操作（复用已有 CRUD 接口） ----------

export async function createAsset(data: AssetCreatePayload): Promise<Asset> {
  const res = await api.post<Asset>('/assets', data)
  return res.data
}

export async function updateAsset(id: number, data: AssetUpdatePayload): Promise<Asset> {
  const res = await api.patch<Asset>(`/assets/${id}`, data)
  return res.data
}

export async function deleteAsset(id: number): Promise<void> {
  await api.delete(`/assets/${id}`)
}

export async function createComponent(data: ComponentCreatePayload): Promise<Component> {
  const res = await api.post<Component>('/components', data)
  return res.data
}

export async function updateComponent(id: number, data: ComponentUpdatePayload): Promise<Component> {
  const res = await api.patch<Component>(`/components/${id}`, data)
  return res.data
}

export async function deleteComponent(id: number): Promise<void> {
  await api.delete(`/components/${id}`)
}

// 上传物料表（rows 已由前端解析），返回预览 + 批次号。
export async function uploadImport(
  rows: ImportRow[],
  file_name: string | null,
): Promise<ImportUploadResponse> {
  const res = await api.post<ImportUploadResponse>('/import/upload', { file_name, rows })
  return res.data
}

// 确认入库：把 previewed 批次落库，返回每行结果。
export async function confirmImport(batchId: number): Promise<ImportConfirmResponse> {
  const res = await api.post<ImportConfirmResponse>('/import/confirm', { batch_id: batchId })
  return res.data
}

// 导入批次历史（admin 看全部，其余角色只看自己的）。
export async function fetchImportBatches(): Promise<{ total: number; items: ImportBatch[] }> {
  const res = await api.get<{ total: number; items: ImportBatch[] }>('/import/batches')
  return res.data
}

// 导出备份快照（仅管理员，只读）：机柜 / 资产 / 部件三层业务键。
export async function fetchExportSnapshot(): Promise<ExportSnapshot> {
  const res = await api.get<ExportSnapshot>('/export/snapshot')
  return res.data
}
