import { useEffect, useRef, useState } from 'react'
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  message,
  Modal,
  Progress,
  Space,
  Spin,
  Table,
  Tag,
  Timeline,
  Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'
import {
  ArrowLeftOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { getErrorMessage } from '../api/client'
import {
  deleteAsset,
  deleteComponent,
  fetchAssetChangelogs,
  fetchAssets,
  fetchComponents,
} from '../api'
import type { Asset, CabinetSummary, ChangeLogEntry, Component, UserInfo } from '../api/types'
import CabinetView from './CabinetView'
import AssetCreateModal from './AssetCreateModal'
import AssetEditModal from './AssetEditModal'
import ComponentFormModal from './ComponentFormModal'

const TYPE_LABEL: Record<string, string> = { server: '服务器', switch: '交换机' }
const STATUS_LABEL: Record<string, string> = { in_use: '在用' }
const SOURCE_LABEL: Record<string, string> = { manual: '手工', import: '导入', bmc: 'BMC' }
const SOURCE_COLOR: Record<string, string> = { manual: 'blue', import: 'green', bmc: 'purple' }
const LOG_ACTION_LABEL: Record<string, string> = { create: '创建', update: '更新', delete: '删除' }
const LOG_ACTION_COLOR: Record<string, string> = { create: 'green', update: 'blue', delete: 'red' }

function fmt(v: string | null | undefined): string {
  return v === null || v === undefined || v === '' ? '—' : v
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function uText(a: Asset): string {
  if (a.u_start == null || a.u_end == null) return '—'
  return a.u_start === a.u_end ? `${a.u_start}U` : `${a.u_start}-${a.u_end}U`
}

function assetLabel(a: Asset): string {
  return a.model || a.sn || a.asset_tag || TYPE_LABEL[a.type] || a.type
}

function sourceTag(fs: Record<string, string>, key: string) {
  const s = fs?.[key]
  if (!s) return null
  return (
    <Tag color={SOURCE_COLOR[s] ?? 'default'} style={{ marginLeft: 6, fontSize: 11 }}>
      {SOURCE_LABEL[s] ?? s}
    </Tag>
  )
}

interface CabinetDrawerProps {
  cabinet: CabinetSummary | null
  user: UserInfo
  initialAssetId?: number | null
  onClose: () => void
  onChanged?: () => void
}

export default function CabinetDrawer({
  cabinet,
  user,
  initialAssetId,
  onClose,
  onChanged,
}: CabinetDrawerProps) {
  return (
    <Drawer
      open={cabinet !== null}
      onClose={onClose}
      width={760}
      destroyOnClose
      title={cabinet ? `机柜 ${cabinet.name}` : ''}
    >
      {cabinet && (
        <CabinetBody
          key={cabinet.id}
          cabinet={cabinet}
          user={user}
          initialAssetId={initialAssetId}
          onChanged={onChanged}
        />
      )}
    </Drawer>
  )
}

function CabinetBody({
  cabinet,
  user,
  initialAssetId,
  onChanged,
}: {
  cabinet: CabinetSummary
  user: UserInfo
  initialAssetId?: number | null
  onChanged?: () => void
}) {
  const [view, setView] = useState<'cabinet' | 'asset'>('cabinet')
  const [assets, setAssets] = useState<Asset[]>([])
  const [assetsLoading, setAssetsLoading] = useState(true)
  const [selected, setSelected] = useState<Asset | null>(null)
  const [components, setComponents] = useState<Component[]>([])
  const [componentsLoading, setComponentsLoading] = useState(false)
  const [logs, setLogs] = useState<ChangeLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [editAsset, setEditAsset] = useState<Asset | null>(null)
  const [compOpen, setCompOpen] = useState(false)
  const [editingComponent, setEditingComponent] = useState<Component | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createU, setCreateU] = useState(1)

  // 与后端 can_manage_cabinet 对齐：admin 全权 / 该柜柜主本人。
  const canManage =
    user.role === 'admin' ||
    (user.role === 'cabinet_owner' && cabinet.owner_id === user.id)

  function reloadAssets() {
    fetchAssets(cabinet.id)
      .then(setAssets)
      .catch(() => setAssets([]))
  }

  function reloadComponents(assetId: number) {
    setComponents([])
    setComponentsLoading(true)
    fetchComponents(assetId)
      .then(setComponents)
      .catch(() => setComponents([]))
      .finally(() => setComponentsLoading(false))
  }

  function reloadLogs(assetId: number) {
    setLogs([])
    setLogsLoading(true)
    fetchAssetChangelogs(assetId)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLogsLoading(false))
  }

  useEffect(() => {
    setAssetsLoading(true)
    fetchAssets(cabinet.id)
      .then(setAssets)
      .catch(() => setAssets([]))
      .finally(() => setAssetsLoading(false))
  }, [cabinet.id])

  function openAsset(a: Asset) {
    setSelected(a)
    setView('asset')
    reloadComponents(a.id)
    reloadLogs(a.id)
  }

  // 搜索跳转：资产列表加载后，若命中目标设备则自动打开其详情（每个 id 只触发一次）。
  const lastOpenedInitial = useRef<number | null>(null)
  useEffect(() => {
    if (initialAssetId == null || lastOpenedInitial.current === initialAssetId) return
    const target = assets.find((x) => x.id === initialAssetId)
    if (target) {
      lastOpenedInitial.current = initialAssetId
      openAsset(target)
    }
  }, [assets, initialAssetId])

  function onAssetSaved(updated: Asset) {
    setSelected(updated)
    setAssets((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
    reloadLogs(updated.id)
    onChanged?.()
  }

  function onPlace(u: number) {
    setCreateU(u)
    setCreateOpen(true)
  }

  function onCreateSaved() {
    reloadAssets()
    onChanged?.()
  }

  function confirmDeleteAsset(a: Asset) {
    Modal.confirm({
      title: `删除设备 ${assetLabel(a)}？`,
      content: '该设备及其下部件将被一并删除（软删除）。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteAsset(a.id)
          message.success('已删除')
          onChanged?.()
          setView('cabinet')
          setSelected(null)
          reloadAssets()
        } catch (e) {
          message.error(getErrorMessage(e, '删除失败'))
        }
      },
    })
  }

  function confirmDeleteComponent(c: Component) {
    Modal.confirm({
      title: `删除部件 ${c.sn || c.category}？`,
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteComponent(c.id)
          message.success('已删除')
          reloadComponents(c.asset_id)
        } catch (e) {
          message.error(getErrorMessage(e, '删除失败'))
        }
      },
    })
  }

  // ---------- 机柜视图 ----------
  if (view === 'cabinet') {
    const usedU = assets.reduce(
      (sum, x) => (x.u_start != null && x.u_end != null ? sum + (x.u_end - x.u_start + 1) : sum),
      0,
    )
    const pct = cabinet.total_u > 0 ? Math.round((usedU / cabinet.total_u) * 100) : 0
    const assetColumns: TableColumnsType<Asset> = [
      {
        title: '设备',
        dataIndex: 'model',
        render: (_, a) => <Typography.Text strong>{assetLabel(a)}</Typography.Text>,
      },
      {
        title: '类型',
        dataIndex: 'type',
        width: 76,
        render: (v: string) => <Tag color={v === 'switch' ? 'orange' : 'blue'}>{TYPE_LABEL[v] ?? v}</Tag>,
      },
      { title: 'U位', width: 72, render: (_, a) => uText(a) },
      { title: 'SN', dataIndex: 'sn', width: 130, render: fmt },
    ]
    return (
      <>
        <Space size={16} wrap style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary">机房：{cabinet.room_code ?? '—'}</Typography.Text>
          <Typography.Text type="secondary">柜主：{cabinet.owner_name ?? '未指派'}</Typography.Text>
          <Progress
            percent={pct}
            size="small"
            format={() => `${usedU}/${cabinet.total_u}U`}
            style={{ width: 160, margin: 0 }}
          />
        </Space>

        <Space size={12} style={{ marginBottom: 12 }}>
          <Typography.Text type="secondary">图例：</Typography.Text>
          <Tag color="blue">服务器</Tag>
          <Tag color="orange">交换机</Tag>
        </Space>

        <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
          <div
            style={{
              maxHeight: 'calc(100vh - 300px)',
              overflowY: 'auto',
              border: '1px solid #f0f0f0',
              borderRadius: 6,
              padding: 8,
            }}
          >
            {assetsLoading ? (
              <div style={{ padding: 40 }}>
                <Spin />
              </div>
            ) : (
              <CabinetView
                assets={assets}
                totalU={cabinet.total_u}
                onSelect={openAsset}
                onPlace={canManage ? onPlace : undefined}
              />
            )}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
              设备（{assets.length}）
            </Typography.Text>
            {assets.length === 0 && !assetsLoading ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该机柜暂无设备" />
            ) : (
              <Table
                rowKey="id"
                columns={assetColumns}
                dataSource={assets}
                size="small"
                pagination={false}
                onRow={(a) => ({ onClick: () => openAsset(a), style: { cursor: 'pointer' } })}
              />
            )}
          </div>
        </div>

        {createOpen && (
          <AssetCreateModal
            cabinetId={cabinet.id}
            cabinetName={cabinet.name}
            uStart={createU}
            onClose={() => setCreateOpen(false)}
            onSaved={onCreateSaved}
          />
        )}
      </>
    )
  }

  // ---------- 资产详情 ----------
  const a = selected
  if (!a) return null
  const compColumns: TableColumnsType<Component> = [
    { title: '物料类型', dataIndex: 'category', width: 90 },
    { title: 'SN', dataIndex: 'sn', width: 130, render: fmt },
    { title: '名称', dataIndex: 'name', render: fmt },
    { title: '物料编码', dataIndex: 'material_code', width: 120, render: fmt },
    { title: '数量', dataIndex: 'qty', width: 60 },
    { title: '挂账人', dataIndex: 'holder_name', width: 110, render: fmt },
  ]
  if (canManage) {
    compColumns.push({
      title: '操作',
      width: 110,
      render: (_: unknown, c: Component) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingComponent(c)
              setCompOpen(true)
            }}
          />
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => confirmDeleteComponent(c)}
          />
        </Space>
      ),
    })
  }
  return (
    <>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => setView('cabinet')}
        style={{ paddingLeft: 0, marginBottom: 8 }}
      >
        返回机柜
      </Button>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 12,
        }}
      >
        <Space>
          <Tag color={a.type === 'switch' ? 'orange' : 'blue'}>{TYPE_LABEL[a.type] ?? a.type}</Tag>
          <Typography.Text strong style={{ fontSize: 16 }}>
            {assetLabel(a)}
          </Typography.Text>
        </Space>
        {canManage && (
          <Space>
            <Button size="small" icon={<EditOutlined />} onClick={() => setEditAsset(a)}>
              编辑
            </Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => confirmDeleteAsset(a)}>
              删除
            </Button>
          </Space>
        )}
      </div>

      <Descriptions column={2} size="small" bordered style={{ marginBottom: 16 }}>
        <Descriptions.Item label="型号">{fmt(a.model)}</Descriptions.Item>
        <Descriptions.Item label="类型">{TYPE_LABEL[a.type] ?? a.type}</Descriptions.Item>
        <Descriptions.Item label="SN">
          {fmt(a.sn)}
          {sourceTag(a.field_source, 'sn')}
        </Descriptions.Item>
        <Descriptions.Item label="CPU型号">
          {fmt(a.cpu_model)}
          {sourceTag(a.field_source, 'cpu_model')}
        </Descriptions.Item>
        <Descriptions.Item label="资产标签">{fmt(a.asset_tag)}</Descriptions.Item>
        <Descriptions.Item label="U位">{uText(a)}</Descriptions.Item>
        <Descriptions.Item label="带内IP">
          {fmt(a.ip_inband)}
          {sourceTag(a.field_source, 'ip_inband')}
        </Descriptions.Item>
        <Descriptions.Item label="BMC IP">
          {fmt(a.bmc_ip)}
          {sourceTag(a.field_source, 'bmc_ip')}
        </Descriptions.Item>
        <Descriptions.Item label="状态">{STATUS_LABEL[a.status] ?? a.status}</Descriptions.Item>
        {a.type === 'switch' && (
          <Descriptions.Item label="挂账人">{fmt(a.holder_name)}</Descriptions.Item>
        )}
        <Descriptions.Item label="备注" span={2}>
          {fmt(a.remark)}
        </Descriptions.Item>
      </Descriptions>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <Typography.Text strong>部件（{components.length}）</Typography.Text>
        {canManage && (
          <Button
            size="small"
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingComponent(null)
              setCompOpen(true)
            }}
          >
            添加部件
          </Button>
        )}
      </div>
      {componentsLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : components.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该设备暂无部件" />
      ) : (
        <Table
          rowKey="id"
          columns={compColumns}
          dataSource={components}
          size="small"
          pagination={{ pageSize: 10, showSizeChanger: true }}
        />
      )}

      <Typography.Text strong style={{ display: 'block', margin: '16px 0 8px' }}>
        变更日志（{logs.length}）
      </Typography.Text>
      {logsLoading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 16 }}>
          <Spin />
        </div>
      ) : logs.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无变更记录" />
      ) : (
        <div style={{ maxHeight: 260, overflowY: 'auto', paddingLeft: 4 }}>
          <Timeline
            items={logs.map((l) => ({
              key: l.id,
              color: LOG_ACTION_COLOR[l.action] ?? 'gray',
              children: (
                <div>
                  <div>
                    <Tag color={LOG_ACTION_COLOR[l.action] ?? 'default'}>
                      {LOG_ACTION_LABEL[l.action] ?? l.action}
                    </Tag>
                    {l.field && (
                      <>
                        <Typography.Text code style={{ fontSize: 12 }}>
                          {l.field}
                        </Typography.Text>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {' '}
                          {l.old_value ?? '—'} → {l.new_value ?? '—'}
                        </Typography.Text>
                      </>
                    )}
                  </div>
                  <div style={{ marginTop: 2 }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {fmtTime(l.created_at)} · {l.operator_name ?? '—'}
                    </Typography.Text>
                    <Tag
                      color={SOURCE_COLOR[l.source] ?? 'default'}
                      style={{ marginLeft: 6, fontSize: 11 }}
                    >
                      {SOURCE_LABEL[l.source] ?? l.source}
                    </Tag>
                  </div>
                </div>
              ),
            }))}
          />
        </div>
      )}

      <AssetEditModal
        asset={editAsset}
        onClose={() => setEditAsset(null)}
        onSaved={onAssetSaved}
      />
      {compOpen && (
        <ComponentFormModal
          assetId={a.id}
          component={editingComponent}
          onClose={() => setCompOpen(false)}
          onSaved={() => reloadComponents(a.id)}
        />
      )}
    </>
  )
}
