import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  message,
} from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { getErrorMessage } from '../api/client'
import {
  assignOwner,
  createCabinet,
  createRoom,
  deleteCabinet,
  deleteRoom,
  fetchCabinetOwners,
  fetchCabinets,
  fetchRooms,
  updateCabinet,
  updateRoom,
} from '../api'
import type { Cabinet, OwnerOption, Room } from '../api/types'

interface RoomFormValues {
  city?: string
  code: string
  zone?: string
  remark?: string
}

interface CabinetFormValues {
  room_id: number
  name: string
  row_no?: string
  col_no?: number
  total_u: number
  owner_id?: number | null
}

export default function CabinetManagePage() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [cabinets, setCabinets] = useState<Cabinet[]>([])
  const [owners, setOwners] = useState<OwnerOption[]>([])
  const [loading, setLoading] = useState(true)
  const [activeKey, setActiveKey] = useState<string>('cabinets')

  // 机柜新增/编辑表单
  const [cabinetModal, setCabinetModal] = useState<{ editing: Cabinet | null } | null>(null)
  const [cabinetForm] = Form.useForm<CabinetFormValues>()
  const [cabinetSaving, setCabinetSaving] = useState(false)

  // 机房新增/编辑表单
  const [roomModal, setRoomModal] = useState<{ editing: Room | null } | null>(null)
  const [roomForm] = Form.useForm<RoomFormValues>()
  const [roomSaving, setRoomSaving] = useState(false)

  // 批量指派柜主
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchOwnerId, setBatchOwnerId] = useState<number | null | undefined>(undefined)
  const [assigning, setAssigning] = useState(false)

  const loadRooms = useCallback(async () => {
    try {
      setRooms(await fetchRooms())
    } catch (e) {
      message.error(getErrorMessage(e, '加载机房失败'))
    }
  }, [])

  const loadCabinets = useCallback(async () => {
    setLoading(true)
    try {
      setCabinets(await fetchCabinets())
    } catch (e) {
      message.error(getErrorMessage(e, '加载机柜失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadOwners = useCallback(async () => {
    try {
      setOwners(await fetchCabinetOwners())
    } catch (e) {
      message.error(getErrorMessage(e, '加载柜主列表失败'))
    }
  }, [])

  useEffect(() => {
    void loadRooms()
    void loadCabinets()
    void loadOwners()
  }, [loadRooms, loadCabinets, loadOwners])

  const roomOptions = useMemo(
    () => rooms.map((r) => ({ value: r.id, label: r.code })),
    [rooms],
  )
  const ownerOptions = useMemo(
    () => owners.map((o) => ({ value: o.id, label: `${o.name}（${o.employee_no}）` })),
    [owners],
  )

  // ---------- 机房 ----------

  function openRoomModal(room: Room | null) {
    setRoomModal({ editing: room })
    roomForm.resetFields()
    if (room) {
      roomForm.setFieldsValue({ city: room.city ?? '', code: room.code, zone: room.zone ?? '', remark: room.remark ?? '' })
    }
  }

  async function onSubmitRoom(values: RoomFormValues) {
    setRoomSaving(true)
    try {
      if (roomModal?.editing) {
        await updateRoom(roomModal.editing.id, values)
        message.success('已保存')
      } else {
        await createRoom(values)
        message.success('已新增')
      }
      setRoomModal(null)
      void loadRooms()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setRoomSaving(false)
    }
  }

  function confirmDeleteRoom(room: Room) {
    Modal.confirm({
      title: `删除机房「${room.code}」？`,
      content: '机房内若仍有未删除的机柜，将无法删除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteRoom(room.id)
          message.success('已删除')
          void loadRooms()
        } catch (e) {
          message.error(getErrorMessage(e, '删除失败'))
        }
      },
    })
  }

  // ---------- 机柜 ----------

  function openCabinetModal(cabinet: Cabinet | null) {
    setCabinetModal({ editing: cabinet })
    cabinetForm.resetFields()
    if (cabinet) {
      cabinetForm.setFieldsValue({
        room_id: cabinet.room_id,
        name: cabinet.name,
        row_no: cabinet.row_no ?? '',
        col_no: cabinet.col_no ?? undefined,
        total_u: cabinet.total_u,
        owner_id: cabinet.owner_id ?? undefined,
      })
    } else {
      cabinetForm.setFieldsValue({ total_u: 45 })
    }
  }

  async function onSubmitCabinet(values: CabinetFormValues) {
    setCabinetSaving(true)
    try {
      const payload = { ...values, owner_id: values.owner_id ?? null }
      if (cabinetModal?.editing) {
        await updateCabinet(cabinetModal.editing.id, payload)
        message.success('已保存')
      } else {
        await createCabinet(payload)
        message.success('已新增')
      }
      setCabinetModal(null)
      void loadCabinets()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setCabinetSaving(false)
    }
  }

  function confirmDeleteCabinet(cabinet: Cabinet) {
    Modal.confirm({
      title: `删除机柜「${cabinet.name}」？`,
      content: '机柜内若仍有未删除的设备，将无法删除。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteCabinet(cabinet.id)
          message.success('已删除')
          void loadCabinets()
        } catch (e) {
          message.error(getErrorMessage(e, '删除失败'))
        }
      },
    })
  }

  async function onAssignOwner() {
    const ids = selectedRowKeys.map((k) => Number(k))
    if (ids.length === 0) {
      message.warning('请先勾选要指派的机柜')
      return
    }
    setAssigning(true)
    try {
      const ownerId = batchOwnerId ?? null
      const { updated } = await assignOwner(ids, ownerId)
      message.success(`已更新 ${updated} 台机柜`)
      setSelectedRowKeys([])
      setBatchOwnerId(undefined)
      void loadCabinets()
    } catch (e) {
      message.error(getErrorMessage(e, '指派失败'))
    } finally {
      setAssigning(false)
    }
  }

  // ---------- 表格列 ----------

  const roomColumns: TableColumnsType<Room> = [
    { title: '城市', dataIndex: 'city', width: 120, render: (v) => v ?? '—' },
    { title: '机房编码', dataIndex: 'code', width: 160 },
    { title: '区域', dataIndex: 'zone', width: 140, render: (v) => v ?? '—' },
    { title: '备注', dataIndex: 'remark', render: (v) => v ?? '—' },
    {
      title: '操作',
      width: 140,
      render: (_, room) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openRoomModal(room)}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => confirmDeleteRoom(room)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const cabinetColumns: TableColumnsType<Cabinet> = [
    { title: '机柜名', dataIndex: 'name', width: 160 },
    { title: '所属机房', dataIndex: 'room_code', width: 140, render: (v) => v ?? '—' },
    { title: '行', dataIndex: 'row_no', width: 70, render: (v) => v ?? '—' },
    { title: '列', dataIndex: 'col_no', width: 70, render: (v) => v ?? '—' },
    { title: '总U', dataIndex: 'total_u', width: 70 },
    {
      title: '柜主',
      dataIndex: 'owner_name',
      width: 140,
      render: (v) => (v ? <Tag color="blue">{v}</Tag> : <Tag>未指派</Tag>),
    },
    {
      title: '操作',
      width: 140,
      render: (_, cabinet) => (
        <Space size={0}>
          <Button type="link" size="small" onClick={() => openCabinetModal(cabinet)}>
            编辑
          </Button>
          <Button type="link" size="small" danger onClick={() => confirmDeleteCabinet(cabinet)}>
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const roomsTab = (
    <Card
      title="机房管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openRoomModal(null)}>
          新增机房
        </Button>
      }
    >
      <Table
        rowKey="id"
        columns={roomColumns}
        dataSource={rooms}
        size="small"
        pagination={false}
      />
    </Card>
  )

  const cabinetsTab = (
    <Card
      title="机柜管理"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openCabinetModal(null)}>
          新增机柜
        </Button>
      }
    >
      <Space style={{ marginBottom: 12, flexWrap: 'wrap' }}>
        <span style={{ color: '#666' }}>已选 {selectedRowKeys.length} 台机柜，批量指派柜主：</span>
        <Select
          allowClear
          placeholder="选择柜主（清空即取消指派）"
          style={{ width: 260 }}
          options={ownerOptions}
          value={batchOwnerId}
          onChange={(v) => setBatchOwnerId(v)}
        />
        <Button type="primary" loading={assigning} onClick={onAssignOwner}>
          应用
        </Button>
      </Space>
      <Table
        rowKey="id"
        columns={cabinetColumns}
        dataSource={cabinets}
        loading={loading}
        size="small"
        pagination={false}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
      />
    </Card>
  )

  return (
    <>
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        items={[
          { key: 'cabinets', label: '机柜管理', children: cabinetsTab },
          { key: 'rooms', label: '机房管理', children: roomsTab },
        ]}
      />

      <Modal
        title={roomModal?.editing ? '编辑机房' : '新增机房'}
        open={roomModal !== null}
        onOk={() => roomForm.submit()}
        onCancel={() => setRoomModal(null)}
        okText="保存"
        cancelText="取消"
        confirmLoading={roomSaving}
      >
        <Form form={roomForm} layout="vertical" onFinish={onSubmitRoom} requiredMark>
          <Form.Item name="city" label="城市">
            <Input placeholder="如 北京" />
          </Form.Item>
          <Form.Item name="code" label="机房编码" rules={[{ required: true, message: '请输入机房编码' }]}>
            <Input placeholder="如 BJ-A1" />
          </Form.Item>
          <Form.Item name="zone" label="区域">
            <Input placeholder="如 1F东侧" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={cabinetModal?.editing ? '编辑机柜' : '新增机柜'}
        open={cabinetModal !== null}
        onOk={() => cabinetForm.submit()}
        onCancel={() => setCabinetModal(null)}
        okText="保存"
        cancelText="取消"
        confirmLoading={cabinetSaving}
      >
        <Form form={cabinetForm} layout="vertical" onFinish={onSubmitCabinet} requiredMark>
          <Form.Item name="room_id" label="所属机房" rules={[{ required: true, message: '请选择机房' }]}>
            <Select options={roomOptions} placeholder="选择机房" />
          </Form.Item>
          <Form.Item name="name" label="机柜名" rules={[{ required: true, message: '请输入机柜名' }]}>
            <Input placeholder="如 A-01" />
          </Form.Item>
          <Space style={{ display: 'flex' }} align="start">
            <Form.Item name="row_no" label="行">
              <Input placeholder="如 A" style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="col_no" label="列">
              <InputNumber min={1} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="total_u" label="总U数">
              <InputNumber min={1} max={100} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item name="owner_id" label="柜主">
            <Select allowClear options={ownerOptions} placeholder="选择柜主（可留空）" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
