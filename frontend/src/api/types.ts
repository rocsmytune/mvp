// 与后端 Pydantic 模型对齐的类型定义。

export interface UserInfo {
  id: number
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

// ---------- 设备 / 部件（只读详情用） ----------

export interface Asset {
  id: number
  type: string // server / switch
  cabinet_id: number | null
  u_start: number | null
  u_end: number | null
  sn: string | null
  asset_tag: string | null
  model: string | null
  cpu_model: string | null
  ip_inband: string | null
  bmc_ip: string | null
  status: string
  in_pool: boolean
  location_raw: string | null
  pool_reason: string | null
  field_source: Record<string, string>
  remark: string | null
  holder_id: number | null
  holder_name: string | null
  created_at: string
  updated_at: string
}

export interface Component {
  id: number
  asset_id: number
  category: string
  sn: string | null
  model: string | null
  name: string | null
  material_code: string | null
  qty: number
  sn_source: string
  remark: string | null
  holder_id: number | null
  holder_name: string | null
  updated_at: string
}

// ---------- 编辑入口写操作 payload（与后端 Pydantic 对齐，可选字段全部可空） ----------

export interface AssetUpdatePayload {
  sn?: string | null
  model?: string | null
  cpu_model?: string | null
  asset_tag?: string | null
  ip_inband?: string | null
  bmc_ip?: string | null
  u_start?: number | null
  u_end?: number | null
  status?: string | null
  remark?: string | null
}

export interface AssetCreatePayload {
  type: 'server' | 'switch'
  cabinet_id: number
  u_start: number
  u_end: number
  sn?: string | null
  asset_tag?: string | null
  model?: string | null
  cpu_model?: string | null
  ip_inband?: string | null
  bmc_ip?: string | null
  status?: string
  remark?: string | null
}

export interface ComponentCreatePayload {
  asset_id: number
  category: string
  sn?: string | null
  model?: string | null
  qty?: number
  remark?: string | null
}

export interface ComponentUpdatePayload {
  category?: string | null
  sn?: string | null
  model?: string | null
  qty?: number | null
  remark?: string | null
}

// ---------- 变更日志 ----------

export interface ChangeLogEntry {
  id: number
  target_type: string
  target_id: number
  action: string // create / update / delete
  field: string | null
  old_value: string | null
  new_value: string | null
  source: string
  operator_id: number | null
  operator_name: string | null
  batch_id: number | null
  created_at: string
}

// ---------- 手工物料导入 ----------

// 8 列原始行（与后端 importer.parse 的键一致）
export interface ImportRow {
  bmc_ip: string | null
  machine_sn: string | null
  material_type: string | null
  sn: string | null
  material_code: string | null
  material_name: string | null
  remark: string | null
  holder: string | null
}

export interface FieldChange {
  field: string
  old: string | null
  new: string | null
}

export interface RowIssue {
  severity: string
  message: string
}

export interface ImportPreviewRow {
  row_no: number
  action: string // new / update / error
  material_type: string | null
  sn: string | null
  bmc_ip: string | null
  machine_sn: string | null
  asset_id: number | null
  asset_sn: string | null
  cabinet_name: string | null
  u_start: number | null
  u_end: number | null
  holder_name: string | null
  changes: FieldChange[]
  issues: RowIssue[]
}

export interface ImportSummary {
  total: number
  new: number
  update: number
  error: number
  warning: number
}

export interface ImportUploadResponse {
  batch_id: number
  file_name: string | null
  summary: ImportSummary
  rows: ImportPreviewRow[]
}

export interface ImportConfirmRow {
  row_no: number
  action: string
  result: string // created / updated / skipped
  message: string | null
}

export interface ImportConfirmResponse {
  batch_id: number
  status: string
  summary: { total: number; created: number; updated: number; skipped: number }
  rows: ImportConfirmRow[]
}

export interface ImportBatch {
  id: number
  file_name: string | null
  status: string // previewed / committed
  operator_id: number | null
  created_at: string
  summary_json: {
    rows?: ImportRow[]
    summary?: ImportSummary
    result?: { created: number; updated: number; skipped: number }
  } | null
}

// ---------- 导出备份 ----------

export interface ExportCabinet {
  room_code: string | null
  name: string
  total_u: number
  owner_employee_no: string | null
  owner_name: string | null
}

export interface ExportAsset {
  room_code: string | null
  cabinet_name: string | null
  type: string // 整机 / 交换机
  u_start: number | null
  u_end: number | null
  sn: string | null
  asset_tag: string | null
  model: string | null
  cpu_model: string | null
  ip_inband: string | null
  bmc_ip: string | null
  status: string
  holder_employee_no: string | null
  holder_name: string | null
  remark: string | null
}

export interface ExportComponent {
  bmc_ip: string | null
  machine_sn: string | null
  material_type: string
  sn: string | null
  material_code: string | null
  material_name: string | null
  remark: string | null
  holder: string | null
}

export interface ExportSnapshot {
  cabinets: ExportCabinet[]
  assets: ExportAsset[]
  components: ExportComponent[]
}
