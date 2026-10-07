import { api } from './client'
import type {
  Asset,
  AssetUpdatePayload,
  Component,
  ComponentCreatePayload,
  ComponentUpdatePayload,
  ExportSnapshot,
  ImportBatch,
  ImportConfirmResponse,
  ImportRow,
  ImportUploadResponse,
  Overview,
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

// ---------- 编辑入口：资产/部件写操作（复用已有 CRUD 接口） ----------

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

// 导出备份快照（仅总管理员，只读）：机柜 / 资产 / 部件三层业务键。
export async function fetchExportSnapshot(): Promise<ExportSnapshot> {
  const res = await api.get<ExportSnapshot>('/export/snapshot')
  return res.data
}
