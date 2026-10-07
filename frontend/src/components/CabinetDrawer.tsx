import { useEffect, useState } from 'react'
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Progress,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { fetchAssets, fetchComponents } from '../api'
import type { Asset, CabinetSummary, Component } from '../api/types'
import CabinetView from './CabinetView'

const TYPE_LABEL: Record<string, string> = { server: '服务器', switch: '交换机' }
const STATUS_LABEL: Record<string, string> = { in_use: '在用' }
const SOURCE_LABEL: Record<string, string> = { manual: '手工', import: '导入', bmc: 'BMC' }
const SOURCE_COLOR: Record<string, string> = { manual: 'blue', import: 'green', bmc: 'purple' }

function fmt(v: string | null | undefined): string {
  return v === null || v === undefined || v === '' ? '—' : v
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
  onClose: () => void
}

export default function CabinetDrawer({ cabinet, onClose }: CabinetDrawerProps) {
  return (
    <Drawer
      open={cabinet !== null}
      onClose={onClose}
      width={760}
      destroyOnClose
      title={cabinet ? `机柜 ${cabinet.name}` : ''}
    >
      {cabinet && <CabinetBody key={cabinet.id} cabinet={cabinet} />}
    </Drawer>
  )
}

function CabinetBody({ cabinet }: { cabinet: CabinetSummary }) {
  const [view, setView] = useState<'cabinet' | 'asset'>('cabinet')
  const [assets, setAssets] = useState<Asset[]>([])
  const [assetsLoading, setAssetsLoading] = useState(true)
  const [selected, setSelected] = useState<Asset | null>(null)
  const [components, setComponents] = useState<Component[]>([])
  const [componentsLoading, setComponentsLoading] = useState(false)

  useEffect(() => {
    fetchAssets(cabinet.id)
      .then(setAssets)
      .catch(() => setAssets([]))
      .finally(() => setAssetsLoading(false))
  }, [cabinet.id])

  function openAsset(a: Asset) {
    setSelected(a)
    setView('asset')
    setComponents([])
    setComponentsLoading(true)
    fetchComponents(a.id)
      .then(setComponents)
      .catch(() => setComponents([]))
      .finally(() => setComponentsLoading(false))
  }

  // ---------- 机柜视图 ----------
  if (view === 'cabinet') {
    const pct =
      cabinet.total_u > 0 ? Math.round((cabinet.used_u / cabinet.total_u) * 100) : 0
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
            format={() => `${cabinet.used_u}/${cabinet.total_u}U`}
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
              <CabinetView assets={assets} totalU={cabinet.total_u} onSelect={openAsset} />
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

      <Space style={{ marginBottom: 12 }}>
        <Tag color={a.type === 'switch' ? 'orange' : 'blue'}>{TYPE_LABEL[a.type] ?? a.type}</Tag>
        <Typography.Text strong style={{ fontSize: 16 }}>
          {assetLabel(a)}
        </Typography.Text>
      </Space>

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

      <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
        部件（{components.length}）
      </Typography.Text>
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
    </>
  )
}
