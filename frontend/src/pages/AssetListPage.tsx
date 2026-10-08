import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Input, Select, Space, Table, Tabs, Tag, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { getErrorMessage } from '../api/client'
import { fetchAssetPage, fetchComponentPage, fetchDictionaries } from '../api'
import type { Asset, Component, Dictionary } from '../api/types'

const TYPE_LABEL: Record<string, string> = { server: '整机', switch: '交换机' }
const TYPE_COLOR: Record<string, string> = { server: 'blue', switch: 'orange' }

function uText(uStart: number | null, uEnd: number | null): string {
  if (uStart == null) return '—'
  return uStart === uEnd ? `${uStart}U` : `${uStart}-${uEnd}U`
}

interface AssetListPageProps {
  onNavigate: (cabinetId: number, assetId: number) => void
}

// 设备 Tab：只读浏览 + 搜索/筛选 + 服务端分页，点击行跳转到机柜详情。
function AssetTab({ onNavigate }: AssetListPageProps) {
  const [rows, setRows] = useState<Asset[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [type, setType] = useState<string | undefined>(undefined)
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [statusOptions, setStatusOptions] = useState<Dictionary[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  useEffect(() => {
    fetchDictionaries('asset_status')
      .then(setStatusOptions)
      .catch(() => setStatusOptions([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAssetPage({
        q: q || undefined,
        type,
        status,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      })
      setRows(res.items)
      setTotal(res.total)
    } catch (e) {
      message.error(getErrorMessage(e, '加载设备失败'))
    } finally {
      setLoading(false)
    }
  }, [q, type, status, page, pageSize])

  useEffect(() => {
    void load()
  }, [load])

  const columns: TableColumnsType<Asset> = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 76,
      render: (v: string) => <Tag color={TYPE_COLOR[v] ?? 'default'}>{TYPE_LABEL[v] ?? v}</Tag>,
    },
    { title: '型号', dataIndex: 'model', width: 140, render: (v) => v || '—' },
    { title: 'SN', dataIndex: 'sn', width: 130, render: (v) => v || '—' },
    { title: '带内IP', dataIndex: 'ip_inband', width: 130, render: (v) => v || '—' },
    { title: 'BMC IP', dataIndex: 'bmc_ip', width: 130, render: (v) => v || '—' },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => {
        const d = statusOptions.find((x) => x.code === v)
        return <Tag>{d?.label ?? v}</Tag>
      },
    },
    { title: '机房', dataIndex: 'room_code', width: 100, render: (v) => v || '—' },
    {
      title: '机柜',
      dataIndex: 'cabinet_name',
      width: 110,
      render: (v) => (v ? v : <Tag>待整理池</Tag>),
    },
    { title: 'U位', width: 80, render: (_, a) => uText(a.u_start, a.u_end) },
    {
      title: '操作',
      width: 70,
      fixed: 'right',
      render: (_, a) => (
        <Button
          type="link"
          size="small"
          disabled={a.cabinet_id == null}
          onClick={() => a.cabinet_id != null && onNavigate(a.cabinet_id, a.id)}
        >
          查看
        </Button>
      ),
    },
  ]

  return (
    <Card
      title="设备列表"
      extra={
        <Space wrap>
          <Input.Search
            placeholder="SN / 资产编号 / IP / 型号"
            allowClear
            style={{ width: 240 }}
            onSearch={(v) => {
              setPage(1)
              setQ(v)
            }}
            onChange={(e) => {
              if (!e.target.value) {
                setPage(1)
                setQ('')
              }
            }}
          />
          <Select
            placeholder="类型"
            allowClear
            style={{ width: 110 }}
            value={type}
            onChange={(v) => {
              setPage(1)
              setType(v)
            }}
            options={[
              { value: 'server', label: '整机' },
              { value: 'switch', label: '交换机' },
            ]}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={status}
            onChange={(v) => {
              setPage(1)
              setStatus(v)
            }}
            options={statusOptions.map((d) => ({ value: d.code, label: d.label }))}
          />
        </Space>
      }
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        scroll={{ x: 1150 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 台`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
    </Card>
  )
}

// 物料 Tab：只读浏览 + 搜索/筛选 + 服务端分页，点击行跳转到所在整机详情。
function ComponentTab({ onNavigate }: AssetListPageProps) {
  const [rows, setRows] = useState<Component[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<string | undefined>(undefined)
  const [categoryOptions, setCategoryOptions] = useState<Dictionary[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  useEffect(() => {
    fetchDictionaries('component_category')
      .then(setCategoryOptions)
      .catch(() => setCategoryOptions([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchComponentPage({
        q: q || undefined,
        category,
        skip: (page - 1) * pageSize,
        limit: pageSize,
      })
      setRows(res.items)
      setTotal(res.total)
    } catch (e) {
      message.error(getErrorMessage(e, '加载物料失败'))
    } finally {
      setLoading(false)
    }
  }, [q, category, page, pageSize])

  useEffect(() => {
    void load()
  }, [load])

  const columns: TableColumnsType<Component> = [
    { title: '物料类型', dataIndex: 'category', width: 100, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '名称/型号', width: 160, render: (_, c) => c.name || c.model || '—' },
    { title: 'SN', dataIndex: 'sn', width: 130, render: (v) => v || '—' },
    { title: '物料编码', dataIndex: 'material_code', width: 120, render: (v) => v || '—' },
    { title: '所在整机', width: 160, render: (_, c) => c.asset_sn || c.asset_model || `#${c.asset_id}` },
    { title: '机房', dataIndex: 'room_code', width: 100, render: (v) => v || '—' },
    { title: '机柜', dataIndex: 'cabinet_name', width: 110, render: (v) => v || '—' },
    { title: '挂账人', dataIndex: 'holder_name', width: 100, render: (v) => v || '—' },
    {
      title: '操作',
      width: 70,
      fixed: 'right',
      render: (_, c) => (
        <Button
          type="link"
          size="small"
          disabled={c.cabinet_id == null}
          onClick={() => c.cabinet_id != null && onNavigate(c.cabinet_id, c.asset_id)}
        >
          查看
        </Button>
      ),
    },
  ]

  return (
    <Card
      title="物料列表"
      extra={
        <Space wrap>
          <Input.Search
            placeholder="SN / 型号 / 名称 / 物料编码"
            allowClear
            style={{ width: 260 }}
            onSearch={(v) => {
              setPage(1)
              setQ(v)
            }}
            onChange={(e) => {
              if (!e.target.value) {
                setPage(1)
                setQ('')
              }
            }}
          />
          <Select
            placeholder="物料类型"
            allowClear
            style={{ width: 140 }}
            value={category}
            onChange={(v) => {
              setPage(1)
              setCategory(v)
            }}
            options={categoryOptions.map((d) => ({ value: d.code, label: d.label }))}
          />
        </Space>
      }
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        scroll={{ x: 1200 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 件`,
          onChange: (p, ps) => {
            setPage(p)
            setPageSize(ps)
          },
        }}
      />
    </Card>
  )
}

export default function AssetListPage({ onNavigate }: AssetListPageProps) {
  return (
    <Tabs
      defaultActiveKey="assets"
      items={[
        { key: 'assets', label: '设备', children: <AssetTab onNavigate={onNavigate} /> },
        { key: 'components', label: '物料', children: <ComponentTab onNavigate={onNavigate} /> },
      ]}
    />
  )
}
