// 通用展示格式化：空值统一「—」，U 位与时间统一格式。

export function fmt(v: string | null | undefined): string {
  return v === null || v === undefined || v === '' ? '—' : v
}

export function uText(uStart: number | null | undefined, uEnd: number | null | undefined): string {
  if (uStart == null || uEnd == null) return '—'
  return uStart === uEnd ? `${uStart}U` : `${uStart}-${uEnd}U`
}

export function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
