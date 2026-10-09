import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Space, Table, Tabs, Tag, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { FilterOutlined } from '@ant-design/icons'
import { getErrorMessage } from '../api/client'
import {
  fetchAssetFacets,
  fetchAssetPage,
  fetchComponentFacets,
  fetchComponentPage,
  fetchDictionaries,
} from '../api'
import { TYPE_COLOR, TYPE_LABEL } from '../constants'
import { uText } from '../lib/format'
import FacetFilterDropdown from '../components/FacetFilterDropdown'
import type { FacetOption } from '../components/FacetFilterDropdown'
import AssetEditModal from '../components/AssetEditModal'
import ComponentFormModal from '../components/ComponentFormModal'
import type { Asset, Component, Dictionary, Facets, UserInfo } from '../api/types'

interface AssetListPageProps {
  user: UserInfo
  onNavigate: (cabinetId: number, assetId: number) => void
}

// 业务管理员（系统管理员 / 物料管理员）：具备物料/机柜/导入/导出权限。
const isBusinessAdmin = (role: string) => role === 'system_admin' || role === 'material_admin'

// 列筛选：数据列 key → 后端查询参数名。
const ASSET_FILTER_PARAMS: Record<string, string> = {
  type: 'types',
  model: 'models',
  sn: 'sns',
  ip_inband: 'ip_inbands',
  bmc_ip: 'bmc_ips',
  status: 'statuses',
  remark: 'remarks',
  room_code: 'room_codes',
  cabinet_name: 'cabinet_names',
}

const COMPONENT_FILTER_PARAMS: Record<string, string> = {
  category: 'categories',
  sn: 'sns',
  material_code: 'material_codes',
  holder_name: 'holder_names',
  remark: 'remarks',
  room_code: 'room_codes',
  cabinet_name: 'cabinet_names',
}

function buildParams(filters: Record<string, string[]>, mapping: Record<string, string>) {
  const p: Record<string, string[]> = {}
  for (const [key, vals] of Object.entries(filters)) {
    if (vals.length) p[mapping[key]] = vals
  }
  return p
}

// 生成表头漏斗筛选的列属性（server-side 过滤，antd 不做本地过滤）。
function filterProps(
  key: string,
  filters: Record<string, string[]>,
  facets: Facets,
  labelOf: (v: string) => string,
  applyFilter: (key: string, vals: string[]) => void,
) {
  const selected = filters[key] ?? []
  const options: FacetOption[] = (facets[key] ?? []).map((f) => ({
    value: f.value,
    label: labelOf(f.value),
    count: f.count,
  }))
  return {
    filtered: selected.length > 0,
    filterIcon: () => (
      <FilterOutlined style={{ color: selected.length > 0 ? '#1677ff' : undefined }} />
    ),
    filterDropdown: ({ close }: { close: () => void }) => (
      <FacetFilterDropdown
        options={options}
        selected={selected}
        onApply={(vals) => {
          applyFilter(key, vals)
          close()
        }}
      />
    ),
  }
}

// 判断某行是否可编辑：管理员全权，柜主仅自己的机柜（前端隐藏，后端仍强制校验）。
function canEdit(user: UserInfo, cabinetOwnerId?: number | null): boolean {
  if (isBusinessAdmin(user.role)) return true
  return user.role === 'cabinet_owner' && cabinetOwnerId != null && cabinetOwnerId === user.id
}

// 设备 Tab：浏览 + 表头列筛选 + 服务端分页 + 行内编辑，点击行跳转到机柜详情。
function AssetTab({ user, onNavigate }: AssetListPageProps) {
  const [rows, setRows] = useState<Asset[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<Record<string, string[]>>({})
  const [facets, setFacets] = useState<Facets>({})
  const [statusOptions, setStatusOptions] = useState<Dictionary[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editing, setEditing] = useState<Asset | null>(null)

  useEffect(() => {
    fetchDictionaries('asset_status').then(setStatusOptions).catch(() => setStatusOptions([]))
    fetchAssetFacets().then(setFacets).catch(() => setFacets({}))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAssetPage({
        ...buildParams(filters, ASSET_FILTER_PARAMS),
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
  }, [filters, page, pageSize])

  useEffect(() => {
    void load()
  }, [load])

  const applyFilter = useCallback((key: string, vals: string[]) => {
    setPage(1)
    setFilters((f) => ({ ...f, [key]: vals }))
  }, [])

  const labelOf = useCallback(
    (v: string, key: string) => {
      if (key === 'type') return TYPE_LABEL[v] ?? v
      if (key === 'status') return statusOptions.find((d) => d.code === v)?.label ?? v
      return v
    },
    [statusOptions],
  )

  const columns: TableColumnsType<Asset> = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 76,
      render: (v: string) => <Tag color={TYPE_COLOR[v] ?? 'default'}>{TYPE_LABEL[v] ?? v}</Tag>,
      ...filterProps('type', filters, facets, (v) => labelOf(v, 'type'), applyFilter),
    },
    {
      title: '型号',
      dataIndex: 'model',
      width: 140,
      render: (v) => v || '—',
      ...filterProps('model', filters, facets, (v) => v, applyFilter),
    },
    {
      title: 'SN',
      dataIndex: 'sn',
      width: 130,
      render: (v) => v || '—',
      ...filterProps('sn', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '带内IP',
      dataIndex: 'ip_inband',
      width: 130,
      render: (v) => v || '—',
      ...filterProps('ip_inband', filters, facets, (v) => v, applyFilter),
    },
    {
      title: 'BMC IP',
      dataIndex: 'bmc_ip',
      width: 130,
      render: (v) => v || '—',
      ...filterProps('bmc_ip', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => {
        const d = statusOptions.find((x) => x.code === v)
        return <Tag>{d?.label ?? v}</Tag>
      },
      ...filterProps('status', filters, facets, (v) => labelOf(v, 'status'), applyFilter),
    },
    {
      title: '机房',
      dataIndex: 'room_code',
      width: 100,
      render: (v) => v || '—',
      ...filterProps('room_code', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '机柜',
      dataIndex: 'cabinet_name',
      width: 110,
      render: (v) => (v ? v : <Tag>待整理池</Tag>),
      ...filterProps('cabinet_name', filters, facets, (v) => v, applyFilter),
    },
    { title: 'U位', width: 80, render: (_, a) => uText(a.u_start, a.u_end) },
    {
      title: '备注',
      dataIndex: 'remark',
      width: 150,
      ellipsis: true,
      render: (v) => v || '—',
      ...filterProps('remark', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '操作',
      width: 120,
      fixed: 'right',
      render: (_, a) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            disabled={a.cabinet_id == null}
            onClick={() => a.cabinet_id != null && onNavigate(a.cabinet_id, a.id)}
          >
            查看
          </Button>
          {canEdit(user, a.cabinet_owner_id) && a.cabinet_id != null && (
            <Button type="link" size="small" onClick={() => setEditing(a)}>
              编辑
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Card title="设备列表" extra="点击表头漏斗按列筛选">
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        scroll={{ x: 1300 }}
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
      <AssetEditModal
        asset={editing}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null)
          void load()
        }}
      />
    </Card>
  )
}

// 物料 Tab：浏览 + 表头列筛选 + 服务端分页 + 行内编辑（含「所在整机」迁移），点击行跳转。
function ComponentTab({ user, onNavigate }: AssetListPageProps) {
  const [rows, setRows] = useState<Component[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState<Record<string, string[]>>({})
  const [facets, setFacets] = useState<Facets>({})
  const [categoryOptions, setCategoryOptions] = useState<Dictionary[]>([])
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [editing, setEditing] = useState<Component | null>(null)

  useEffect(() => {
    fetchDictionaries('component_category')
      .then(setCategoryOptions)
      .catch(() => setCategoryOptions([]))
    fetchComponentFacets().then(setFacets).catch(() => setFacets({}))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchComponentPage({
        ...buildParams(filters, COMPONENT_FILTER_PARAMS),
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
  }, [filters, page, pageSize])

  useEffect(() => {
    void load()
  }, [load])

  const applyFilter = useCallback((key: string, vals: string[]) => {
    setPage(1)
    setFilters((f) => ({ ...f, [key]: vals }))
  }, [])

  const labelOf = useCallback(
    (v: string, key: string) => {
      if (key === 'category') return categoryOptions.find((d) => d.code === v)?.label ?? v
      return v
    },
    [categoryOptions],
  )

  const columns: TableColumnsType<Component> = [
    {
      title: '物料类型',
      dataIndex: 'category',
      width: 100,
      render: (v: string) => <Tag color="purple">{v}</Tag>,
      ...filterProps('category', filters, facets, (v) => labelOf(v, 'category'), applyFilter),
    },
    {
      title: '名称/型号',
      width: 160,
      render: (_, c) => c.name || c.model || '—',
    },
    {
      title: 'SN',
      dataIndex: 'sn',
      width: 130,
      render: (v) => v || '—',
      ...filterProps('sn', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '物料编码',
      dataIndex: 'material_code',
      width: 120,
      render: (v) => v || '—',
      ...filterProps('material_code', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '所在整机',
      width: 160,
      render: (_, c) => c.asset_bmc_ip || c.asset_sn || c.asset_model || `#${c.asset_id}`,
    },
    {
      title: '机房',
      dataIndex: 'room_code',
      width: 100,
      render: (v) => v || '—',
      ...filterProps('room_code', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '机柜',
      dataIndex: 'cabinet_name',
      width: 110,
      render: (v) => v || '—',
      ...filterProps('cabinet_name', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '挂账人',
      dataIndex: 'holder_name',
      width: 100,
      render: (v) => v || '—',
      ...filterProps('holder_name', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '备注',
      dataIndex: 'remark',
      width: 150,
      ellipsis: true,
      render: (v) => v || '—',
      ...filterProps('remark', filters, facets, (v) => v, applyFilter),
    },
    {
      title: '操作',
      width: 120,
      fixed: 'right',
      render: (_, c) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            disabled={c.cabinet_id == null}
            onClick={() => c.cabinet_id != null && onNavigate(c.cabinet_id, c.asset_id)}
          >
            查看
          </Button>
          {canEdit(user, c.cabinet_owner_id) && c.cabinet_id != null && (
            <Button type="link" size="small" onClick={() => setEditing(c)}>
              编辑
            </Button>
          )}
        </Space>
      ),
    },
  ]

  return (
    <Card title="物料列表" extra="点击表头漏斗按列筛选">
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        scroll={{ x: 1350 }}
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
      {editing && (
        <ComponentFormModal
          assetId={editing.asset_id}
          component={editing}
          movable
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            void load()
          }}
        />
      )}
    </Card>
  )
}

export default function AssetListPage({ user, onNavigate }: AssetListPageProps) {
  return (
    <Tabs
      defaultActiveKey="assets"
      items={[
        { key: 'assets', label: '设备', children: <AssetTab user={user} onNavigate={onNavigate} /> },
        { key: 'components', label: '物料', children: <ComponentTab user={user} onNavigate={onNavigate} /> },
      ]}
    />
  )
}
