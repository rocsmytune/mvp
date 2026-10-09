import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { AutoComplete, Input, Tag } from 'antd'
import type { InputRef } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { searchGlobal } from '../api'
import type { SearchResult } from '../api/types'

interface Opt {
  value: string
  label: ReactNode
  disabled?: boolean
}

interface GlobalSearchProps {
  onNavigate: (cabinetId: number, assetId: number) => void
}

function locText(r: SearchResult): string {
  if (!r.cabinet_name) return '待整理池'
  const u =
    r.u_start == null ? '—' : r.u_start === r.u_end ? `${r.u_start}U` : `${r.u_start}-${r.u_end}U`
  return `${r.room_code ?? '—'} · ${r.cabinet_name} · ${u} · 柜主 ${r.owner_name ?? '未指派'}`
}

function idText(r: SearchResult): string {
  if (r.kind === 'asset') return r.asset_sn || r.asset_tag || r.model || `#${r.asset_id}`
  return r.component_sn || r.component_name || `#${r.component_id}`
}

export default function GlobalSearch({ onNavigate }: GlobalSearchProps) {
  const [value, setValue] = useState('')
  const [options, setOptions] = useState<Opt[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  const resultMap = useRef(new Map<string, SearchResult>())
  const inputRef = useRef<InputRef>(null)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  // 快捷键「/」聚焦搜索框（内网巡检常用，免鼠标点击）。
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      const typing =
        target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable
      if (e.key === '/' && !typing) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function run(kw: string) {
    setLoading(true)
    searchGlobal(kw)
      .then((rows) => {
        const map = new Map<string, SearchResult>()
        const opts: Opt[] = rows.map((r) => {
          const value = `${r.kind}:${r.asset_id}:${r.component_id ?? 0}`
          map.set(value, r)
          const tag = r.kind === 'asset' ? '整机' : `部件·${r.component_category ?? ''}`
          return {
            value,
            // 待整理池设备无机柜，不可点击跳转
            disabled: r.cabinet_id == null,
            label: (
              <div style={{ padding: '2px 0' }}>
                <div>
                  <Tag color={r.kind === 'asset' ? 'blue' : 'purple'} style={{ marginRight: 4 }}>
                    {tag}
                  </Tag>
                  <span style={{ fontWeight: 500 }}>{idText(r)}</span>
                </div>
                <div style={{ color: '#8c8c8c', fontSize: 12 }}>{locText(r)}</div>
              </div>
            ),
          }
        })
        resultMap.current = map
        setOptions(opts)
        setLoading(false)
        setOpen(true)
      })
      .catch(() => {
        resultMap.current.clear()
        setOptions([])
        setLoading(false)
        setOpen(false)
      })
  }

  function onSearch(text: string) {
    setValue(text)
    window.clearTimeout(timer.current)
    const kw = text.trim()
    if (!kw) {
      resultMap.current.clear()
      setOptions([])
      setLoading(false)
      setOpen(false)
      return
    }
    setOpen(true)
    timer.current = window.setTimeout(() => run(kw), 300)
  }

  function onSelect(sel: string) {
    const r = resultMap.current.get(sel)
    setValue('')
    setOptions([])
    setOpen(false)
    if (r && r.cabinet_id != null) {
      onNavigate(r.cabinet_id, r.asset_id)
    }
  }

  return (
    <AutoComplete
      value={value}
      style={{ width: 280 }}
      options={options}
      open={open}
      onSearch={onSearch}
      onSelect={onSelect}
      onDropdownVisibleChange={(v) => setOpen(v)}
      notFoundContent={loading ? '搜索中…' : '无匹配结果'}
      allowClear
    >
      <Input ref={inputRef} prefix={<SearchOutlined />} placeholder="搜索 SN / IP / 资产编号（按 / 聚焦）" />
    </AutoComplete>
  )
}
