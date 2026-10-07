import * as XLSX from 'xlsx'
import type { ExportSnapshot, ImportRow } from '../api/types'

// 表头别名 → 内部字段。匹配前对表头做「去空白 + 转小写」归一化，兼容常见叫法。
const HEADER_ALIASES: Record<string, keyof ImportRow> = {
  bmcip: 'bmc_ip',
  bmc_ip: 'bmc_ip',
  管理口ip: 'bmc_ip',
  bmc地址: 'bmc_ip',
  整机sn: 'machine_sn',
  机器sn: 'machine_sn',
  整机序列号: 'machine_sn',
  物料类型: 'material_type',
  类型: 'material_type',
  sn: 'sn',
  序列号: 'sn',
  物料编码: 'material_code',
  物料名称: 'material_name',
  名称: 'material_name',
  备注: 'remark',
  挂账人: 'holder',
  挂账: 'holder',
}

// 字段的中文标签，用于错误提示。
const HEADER_LABEL: Record<keyof ImportRow, string> = {
  bmc_ip: 'BMC IP',
  machine_sn: '整机SN',
  material_type: '物料类型',
  sn: 'SN',
  material_code: '物料编码',
  material_name: '物料名称',
  remark: '备注',
  holder: '挂账人',
}

// 定位与分类所需的最小列；缺列则无法导入。
const REQUIRED: Array<keyof ImportRow> = ['bmc_ip', 'material_type', 'sn']

// 8 列表头（单一来源，页面提示与模板下载共用）。
export const IMPORT_HEADERS = [
  'BMC IP',
  '整机SN',
  '物料类型',
  'SN',
  '物料编码',
  '物料名称',
  '备注',
  '挂账人',
]

export interface ExcelParseError extends Error {
  kind: 'empty' | 'header'
  missing?: string[]
}

function normalizeHeader(value: unknown): string {
  return String(value ?? '').trim().replace(/\s+/g, '').toLowerCase()
}

function toCell(value: unknown): string | null {
  const s = String(value ?? '').trim()
  return s === '' ? null : s
}

/**
 * 把上传的 Excel/CSV 二进制解析成 8 列 ImportRow。
 * 表头缺必需列、空文件、无数据行时抛 ExcelParseError，由调用方友好提示。
 */
export function parseImportExcel(buffer: ArrayBuffer): {
  rows: ImportRow[]
  warnings: string[]
} {
  let wb: XLSX.WorkBook
  try {
    wb = XLSX.read(buffer, { type: 'array' })
  } catch {
    const e = new Error('文件无法解析，请确认是 .xlsx / .xls / .csv 格式') as ExcelParseError
    e.kind = 'empty'
    throw e
  }

  const sheetName = wb.SheetNames[0]
  if (!sheetName) {
    const e = new Error('文件为空，没有可读取的工作表') as ExcelParseError
    e.kind = 'empty'
    throw e
  }
  const sheet = wb.Sheets[sheetName]
  const matrix = XLSX.utils.sheet_to_json<unknown[]>(sheet, { header: 1, defval: '' })

  const headerRow = (matrix[0] ?? []) as unknown[]
  const fieldByCol = headerRow.map((h) => HEADER_ALIASES[normalizeHeader(h)] ?? null)

  const missing = REQUIRED.filter((f) => !fieldByCol.includes(f))
  if (missing.length > 0) {
    const e = new Error(
      `表头缺少必需列：${missing.map((m) => HEADER_LABEL[m]).join('、')}，请按模板整理后重新上传`,
    ) as ExcelParseError
    e.kind = 'header'
    e.missing = missing
    throw e
  }

  const rows: ImportRow[] = []
  let skippedEmpty = 0
  for (let r = 1; r < matrix.length; r++) {
    const raw = (matrix[r] ?? []) as unknown[]
    if (raw.every((c) => String(c ?? '').trim() === '')) {
      skippedEmpty++
      continue
    }
    const row: ImportRow = {
      bmc_ip: null,
      machine_sn: null,
      material_type: null,
      sn: null,
      material_code: null,
      material_name: null,
      remark: null,
      holder: null,
    }
    fieldByCol.forEach((field, col) => {
      if (field) row[field] = toCell(raw[col])
    })
    rows.push(row)
  }

  const warnings: string[] = []
  if (skippedEmpty > 0) warnings.push(`已跳过 ${skippedEmpty} 个空白行`)
  if (rows.length === 0) {
    const e = new Error('文件中没有可导入的数据行（表头之后全为空）') as ExcelParseError
    e.kind = 'empty'
    throw e
  }
  return { rows, warnings }
}

// 下载带一行示例的导入模板，降低首次使用的操作门槛。
export function downloadImportTemplate(): void {
  const ws = XLSX.utils.aoa_to_sheet([
    IMPORT_HEADERS,
    ['192.0.2.10', 'SRV-0001', '硬盘', 'DISK-0001', 'MAT-0001', 'SAS 960G', '', '000002 柜主甲'],
  ])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '物料表')
  XLSX.writeFile(wb, '物料导入模板.xlsx')
}

// 导出备份：机柜 / 资产 / 部件三张工作表。部件表复用 8 列导入格式，可直接重新导入。
export function downloadBackup(snapshot: ExportSnapshot): void {
  const wb = XLSX.utils.book_new()

  const cabWs = XLSX.utils.json_to_sheet(
    snapshot.cabinets.map((c) => ({
      机房编码: c.room_code ?? '',
      机柜名: c.name,
      总U: c.total_u,
      柜主工号: c.owner_employee_no ?? '',
      柜主姓名: c.owner_name ?? '',
    })),
  )
  XLSX.utils.book_append_sheet(wb, cabWs, '机柜')

  const assetWs = XLSX.utils.json_to_sheet(
    snapshot.assets.map((a) => ({
      机房编码: a.room_code ?? '',
      机柜名: a.cabinet_name ?? '',
      类型: a.type,
      U起始: a.u_start ?? '',
      U结束: a.u_end ?? '',
      SN: a.sn ?? '',
      资产标签: a.asset_tag ?? '',
      型号: a.model ?? '',
      CPU型号: a.cpu_model ?? '',
      带内IP: a.ip_inband ?? '',
      BMC_IP: a.bmc_ip ?? '',
      状态: a.status,
      挂账人工号: a.holder_employee_no ?? '',
      挂账人姓名: a.holder_name ?? '',
      备注: a.remark ?? '',
    })),
  )
  XLSX.utils.book_append_sheet(wb, assetWs, '资产')

  const compWs = XLSX.utils.json_to_sheet(
    snapshot.components.map((c) => ({
      'BMC IP': c.bmc_ip ?? '',
      整机SN: c.machine_sn ?? '',
      物料类型: c.material_type,
      SN: c.sn ?? '',
      物料编码: c.material_code ?? '',
      物料名称: c.material_name ?? '',
      备注: c.remark ?? '',
      挂账人: c.holder ?? '',
    })),
  )
  XLSX.utils.book_append_sheet(wb, compWs, '部件')

  const date = new Date().toISOString().slice(0, 10)
  XLSX.writeFile(wb, `机柜物料备份_${date}.xlsx`)
}
