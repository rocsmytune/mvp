import { useEffect, useMemo, useState } from 'react'
import { Card, Col, Empty, message, Progress, Row, Select, Space, Spin, Statistic, Typography } from 'antd'
import { fetchOverview } from '../api'
import type { CabinetSummary, Overview, UserInfo } from '../api/types'
import CabinetDrawer from '../components/CabinetDrawer'

interface OverviewPageProps {
  user: UserInfo
  // 全局搜索命中：打开指定机柜抽屉并选中该设备（一次性，消费后回调清空）。
  focus?: { cabinetId: number; assetId: number } | null
  onFocusHandled?: () => void
}

export default function OverviewPage({ user, focus, onFocusHandled }: OverviewPageProps) {
  const [data, setData] = useState<Overview | null>(null)
  const [loading, setLoading] = useState(true)
  const [roomId, setRoomId] = useState<number | undefined>(undefined)
  const [zone, setZone] = useState<string | undefined>(undefined)
  const [selectedCabinet, setSelectedCabinet] = useState<CabinetSummary | null>(null)
  const [focusAssetId, setFocusAssetId] = useState<number | null>(null)

  const load = async () => {
    try {
      setData(await fetchOverview())
    } catch {
      message.error('加载机房总览失败')
    }
  }

  useEffect(() => {
    load().finally(() => setLoading(false))
  }, [])

  // 消费搜索命中：找到机柜开抽屉，并记录要选中的设备。
  useEffect(() => {
    if (!focus || !data) return
    const cab = data.cabinets.find((c) => c.id === focus.cabinetId)
    if (cab) {
      setSelectedCabinet(cab)
      setFocusAssetId(focus.assetId)
    } else {
      message.warning('未找到对应机柜（可能已被删除）')
    }
    onFocusHandled?.()
  }, [focus, data, onFocusHandled])

  const roomById = useMemo(
    () => new Map((data?.rooms ?? []).map((r) => [r.id, r])),
    [data],
  )

  const zones = useMemo(
    () => Array.from(new Set((data?.rooms ?? []).map((r) => r.zone).filter((z): z is string => !!z))),
    [data],
  )

  const cabinets = useMemo(() => {
    if (!data) return []
    return data.cabinets.filter((c) => {
      if (roomId !== undefined && c.room_id !== roomId) return false
      if (zone && roomById.get(c.room_id)?.zone !== zone) return false
      return true
    })
  }, [data, roomId, zone, roomById])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 80 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!data) return null

  const totalDevices = data.placed_count + data.pool_count

  // ← → 切换机柜：基于当前筛选后的机柜顺序，方便连续巡检。
  const cabinetIndex = selectedCabinet ? cabinets.findIndex((c) => c.id === selectedCabinet.id) : -1
  const onPrevCabinet =
    cabinetIndex > 0
      ? () => {
          setSelectedCabinet(cabinets[cabinetIndex - 1])
          setFocusAssetId(null)
        }
      : undefined
  const onNextCabinet =
    cabinetIndex >= 0 && cabinetIndex < cabinets.length - 1
      ? () => {
          setSelectedCabinet(cabinets[cabinetIndex + 1])
          setFocusAssetId(null)
        }
      : undefined

  return (
    <>
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="已上架设备" value={data.placed_count} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="待整理设备" value={data.pool_count} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="设备总数" value={totalDevices} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic title="机柜总数" value={data.cabinets.length} />
          </Card>
        </Col>
      </Row>

      <Card title="机房总览" extra="点击机柜查看 U 位图与设备详情">
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="按机房筛选"
            allowClear
            style={{ width: 260 }}
            value={roomId}
            onChange={(v) => setRoomId(v)}
            options={data.rooms.map((r) => ({ value: r.id, label: r.code }))}
          />
          <Select
            placeholder="按区域筛选"
            allowClear
            style={{ width: 160 }}
            value={zone}
            onChange={(v) => setZone(v)}
            options={zones.map((z) => ({ value: z, label: z }))}
          />
        </Space>

        {cabinets.length === 0 ? (
          <Empty description="暂无符合条件的机柜" />
        ) : (
          <Row gutter={[16, 16]}>
            {cabinets.map((c) => {
              const pct = c.total_u > 0 ? Math.round((c.used_u / c.total_u) * 100) : 0
              const status = pct >= 90 ? 'exception' : pct >= 70 ? 'normal' : 'success'
              return (
                <Col key={c.id} xs={24} sm={12} md={8} lg={6}>
                  <Card
                    size="small"
                    hoverable
                    onClick={() => setSelectedCabinet(c)}
                  >
                    <Space direction="vertical" style={{ width: '100%' }} size={4}>
                      <Typography.Text strong>{c.name}</Typography.Text>
                      <Typography.Text type="secondary">
                        柜主：{c.owner_name ?? '未指派'}
                      </Typography.Text>
                      <Typography.Text type="secondary">设备数：{c.device_count}</Typography.Text>
                      <div>
                        <Progress
                          percent={pct}
                          status={status}
                          size="small"
                          format={() => `${c.used_u}/${c.total_u}U`}
                        />
                      </div>
                    </Space>
                  </Card>
                </Col>
              )
            })}
          </Row>
        )}
      </Card>
    </Space>
    <CabinetDrawer
      cabinet={selectedCabinet}
      user={user}
      initialAssetId={focusAssetId}
      onPrev={onPrevCabinet}
      onNext={onNextCabinet}
      onClose={() => {
        setSelectedCabinet(null)
        setFocusAssetId(null)
      }}
      onChanged={load}
    />
    </>
  )
}
