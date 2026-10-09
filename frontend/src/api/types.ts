// 与后端 Pydantic 模型对齐的类型定义。

export interface UserInfo {
  id: number
  employee_no: string
  name: string
  role: string
}

// ---------- 用户管理（仅系统管理员） ----------

export interface UserAdmin {
  id: number
  employee_no: string
  name: string
  role: string
  active: boolean
  auth_source: string
  created_at: string
}

export interface UserCreatePayload {
  employee_no: string
  name: string
  role: string
  password: string
}

export interface UserUpdatePayload {
  name?: string | null
  role?: string | null
  password?: string | null
  active?: boolean | null
}

// ---------- 字典管理 ----------

export interface Dictionary {
  id: number
  kind: string // asset_status / component_category
  code: string
  label: string
  sort_no: number
  usage_count: number
}

export interface DictionaryUsage {
  target_type: string // asset / component
  sn: string | null
  asset_sn: string | null
  name: string | null
  cabinet_name: string | null
  u_start: number | null
  u_end: number | null
}

export interface DictionaryCreatePayload {
  kind: string
  code: string
  label: string
  sort_no?: number
}

export interface DictionaryUpdatePayload {
  code?: string | null
  label?: string | null
  sort_no?: number | null
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

// ---------- 机柜管理（管理员） ----------

export interface OwnerOption {
  id: number
  employee_no: string
  name: string
}

export interface Cabinet {
  id: number
  room_id: number
  name: string
  row_no: string | null
  col_no: number | null
  total_u: number
  owner_id: number | null
  owner_name: string | null
  room_code: string | null
}

export interface RoomCreatePayload {
  city?: string | null
  code: string
  zone?: string | null
  remark?: string | null
}

export interface RoomUpdatePayload {
  city?: string | null
  code?: string | null
  zone?: string | null
  remark?: string | null
}

export interface CabinetCreatePayload {
  room_id: number
  name: string
  row_no?: string | null
  col_no?: number | null
  total_u?: number
  owner_id?: number | null
}

export interface CabinetUpdatePayload {
  room_id?: number | null
  name?: string | null
  row_no?: string | null
  col_no?: number | null
  total_u?: number | null
  owner_id?: number | null
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
  // 列表页联表返回的定位上下文（详情/写接口可能不含）
  cabinet_name?: string | null
  room_code?: string | null
  cabinet_owner_id?: number | null
}

export interface Component {
  id: number
  asset_id: number
  category: string
  sn: string | null
  model: string | null
  name: string | null
  material_code: string | null
  sn_source: string
  remark: string | null
  holder_id: number | null
  holder_name: string | null
  holder_employee_no?: string | null
  updated_at: string
  // 列表页联表返回的定位上下文
  asset_sn?: string | null
  asset_model?: string | null
  asset_bmc_ip?: string | null
  cabinet_id?: number | null
  cabinet_name?: string | null
  room_code?: string | null
  cabinet_owner_id?: number | null
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
  name?: string | null
  material_code?: string | null
  remark?: string | null
  holder_name?: string | null
}

export interface ComponentUpdatePayload {
  asset_id?: number | null
  category?: string | null
  sn?: string | null
  model?: string | null
  name?: string | null
  material_code?: string | null
  remark?: string | null
  holder_name?: string | null
}

// ---------- 列筛选 facet ----------

export interface FacetValue {
  value: string
  count: number
}

export type Facets = Record<string, FacetValue[]>

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

// ---------- 全局搜索 ----------

export interface SearchResult {
  kind: 'asset' | 'component'
  matched_field: string // sn / asset_tag / ip_inband / bmc_ip / component_sn
  room_code: string | null
  cabinet_id: number | null
  cabinet_name: string | null
  u_start: number | null
  u_end: number | null
  owner_name: string | null
  asset_id: number
  asset_type: string
  asset_sn: string | null
  asset_tag: string | null
  model: string | null
  ip_inband: string | null
  bmc_ip: string | null
  status: string
  in_pool: boolean
  component_id: number | null
  component_category: string | null
  component_sn: string | null
  component_name: string | null
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
  no_change: number
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
