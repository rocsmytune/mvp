import { useEffect, useState } from 'react'
import { Form, Input, InputNumber, Modal, Select, message } from 'antd'
import { getErrorMessage } from '../api/client'
import { createAsset } from '../api'
import type { Asset, AssetCreatePayload } from '../api/types'

const TYPE_OPTIONS = [
  { value: 'server', label: '服务器' },
  { value: 'switch', label: '交换机' },
]
const STATUS_OPTIONS = [{ value: 'in_use', label: '在用' }]

function norm(v: string | null | undefined): string | null {
  if (v === '' || v === undefined) return null
  return v
}

interface Props {
  cabinetId: number
  cabinetName: string
  uStart: number
  onClose: () => void
  onSaved: (asset: Asset) => void
}

export default function AssetCreateModal({ cabinetId, cabinetName, uStart, onClose, onSaved }: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    form.setFieldsValue({
      type: 'server',
      u_start: uStart,
      u_end: uStart,
      status: 'in_use',
      sn: '',
      model: '',
      cpu_model: '',
      asset_tag: '',
      ip_inband: '',
      bmc_ip: '',
      remark: '',
    })
  }, [uStart, form])

  const onSubmit = async () => {
    const values = await form.validateFields()
    const payload: AssetCreatePayload = {
      type: values.type,
      cabinet_id: cabinetId,
      u_start: values.u_start,
      u_end: values.u_end,
      sn: norm(values.sn),
      model: norm(values.model),
      cpu_model: norm(values.cpu_model),
      asset_tag: norm(values.asset_tag),
      ip_inband: norm(values.ip_inband),
      bmc_ip: norm(values.bmc_ip),
      status: values.status ?? 'in_use',
      remark: norm(values.remark),
    }
    setSubmitting(true)
    try {
      const asset = await createAsset(payload)
      message.success('已上架')
      onSaved(asset)
      onClose()
    } catch (e) {
      message.error(getErrorMessage(e, '上架失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open
      title={`在机柜 ${cabinetName} 上架设备`}
      okText="上架"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={onSubmit}
      onCancel={onClose}
      destroyOnClose
      forceRender
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
          <Select options={TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item label="U 位（起 / 止，1–45）" required style={{ marginBottom: 0 }}>
          <Form.Item
            name="u_start"
            rules={[{ required: true, message: '请输入起始 U 位' }]}
            style={{ display: 'inline-block', width: 'calc(50% - 8px)', marginRight: 8 }}
          >
            <InputNumber min={1} max={45} placeholder="起始" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="u_end"
            rules={[{ required: true, message: '请输入结束 U 位' }]}
            style={{ display: 'inline-block', width: 'calc(50% - 8px)' }}
          >
            <InputNumber min={1} max={45} placeholder="结束" style={{ width: '100%' }} />
          </Form.Item>
        </Form.Item>
        <Form.Item label="SN" name="sn">
          <Input placeholder="整机序列号" />
        </Form.Item>
        <Form.Item label="型号" name="model">
          <Input placeholder="型号" />
        </Form.Item>
        <Form.Item label="CPU 型号" name="cpu_model">
          <Input placeholder="CPU 型号" />
        </Form.Item>
        <Form.Item label="资产标签" name="asset_tag">
          <Input placeholder="资产标签" />
        </Form.Item>
        <Form.Item label="带内 IP" name="ip_inband">
          <Input placeholder="带内 IP" />
        </Form.Item>
        <Form.Item label="BMC IP" name="bmc_ip">
          <Input placeholder="BMC / 管理口 IP" />
        </Form.Item>
        <Form.Item label="状态" name="status">
          <Select options={STATUS_OPTIONS} />
        </Form.Item>
        <Form.Item label="备注" name="remark">
          <Input.TextArea rows={2} placeholder="备注" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
