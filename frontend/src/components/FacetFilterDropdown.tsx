import { useEffect, useMemo, useState } from 'react'
import { Button, Checkbox, Input, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'

export interface FacetOption {
  value: string
  label: string
  count: number
}

interface FacetFilterDropdownProps {
  options: FacetOption[]
  selected: string[]
  onApply: (values: string[]) => void
}

// 表头列筛选下拉：Excel 式「去重值 + 计数」复选清单 + 搜索框（本地过滤显示值）。
export default function FacetFilterDropdown({
  options,
  selected,
  onApply,
}: FacetFilterDropdownProps) {
  const [kw, setKw] = useState('')
  const [draft, setDraft] = useState<string[]>(selected)

  // 打开/外部选中态变化时，把草稿同步为当前已选值。
  useEffect(() => {
    setDraft(selected)
  }, [selected])

  const visible = useMemo(() => {
    const k = kw.trim().toLowerCase()
    if (!k) return options
    return options.filter((o) => o.label.toLowerCase().includes(k))
  }, [kw, options])

  return (
    <div style={{ padding: 8, width: 260 }}>
      <Input
        size="small"
        allowClear
        prefix={<SearchOutlined />}
        placeholder="搜索"
        value={kw}
        onChange={(e) => setKw(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <div style={{ maxHeight: 260, overflow: 'auto', marginBottom: 8 }}>
        {visible.length === 0 ? (
          <div style={{ color: '#999', textAlign: 'center', padding: 12 }}>无匹配值</div>
        ) : (
          <Checkbox.Group
            style={{ display: 'flex', flexDirection: 'column' }}
            value={draft}
            onChange={(vals) => setDraft(vals as string[])}
          >
            {visible.map((o) => (
              <Checkbox key={o.value} value={o.value} style={{ marginLeft: 0, padding: '1px 0' }}>
                <span>{o.label}</span>
                <span style={{ color: '#999', marginLeft: 4 }}>({o.count})</span>
              </Checkbox>
            ))}
          </Checkbox.Group>
        )}
      </div>
      <Space>
        <Button size="small" type="primary" onClick={() => onApply(draft)}>
          确定
        </Button>
        <Button
          size="small"
          onClick={() => {
            setDraft([])
            onApply([])
          }}
        >
          重置
        </Button>
      </Space>
    </div>
  )
}
