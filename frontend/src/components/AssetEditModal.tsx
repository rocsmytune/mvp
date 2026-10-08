import { useEffect, useState } from 'react'
import { Form, Input, InputNumber, Modal, Select, message } from 'antd'
import { getErrorMessage } from '../api/client'
import { fetchDictionaries, updateAsset } from '../api'
import type { Asset, AssetUpdatePayload } from '../api/types'

const FALLBACK_STATUS = [{ value: 'in_use', label: '在用' }]

const SOURCE_LABEL: Record<string, string> = { manual: '手工', import: '导入', bmc: 'BMC' }

// 关键字段来源小标（只读提示，不参与编辑）。
function sourceHint(asset: Asset, key: string): string | undefined {
  const s = asset.field_source?.[key]
  return s ? `来源：${SOURCE_LABEL[s] ?? s}` : undefined
}

function norm(v: string | number | null | undefined): string | number | null {
  if (v === '' || v === undefined) return null
  return v
}

interface Props {
  asset: Asset | null
  onClose: () => void
  onSaved: (updated: Asset) => void
}

export default function AssetEditModal({ asset, onClose, onSaved }: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [statusOptions, setStatusOptions] = useState(FALLBACK_STATUS)

  useEffect(() => {
    fetchDictionaries('asset_status')
      .then((dicts) => {
        if (dicts.length > 0) {
          setStatusOptions(dicts.map((d) => ({ value: d.code, label: d.label })))
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (asset) {
      form.setFieldsValue({
        sn: asset.sn ?? '',
        model: asset.model ?? '',
        cpu_model: asset.cpu_model ?? '',
        asset_tag: asset.asset_tag ?? '',
        ip_inband: asset.ip_inband ?? '',
        bmc_ip: asset.bmc_ip ?? '',
        u_start: asset.u_start,
        u_end: asset.u_end,
        status: asset.status,
        remark: asset.remark ?? '',
      })
    }
  }, [asset, form])

  const onSubmit = async () => {
    if (!asset) return
    const values = await form.validateFields()
    const payload: AssetUpdatePayload = {
      sn: norm(values.sn) as string | null,
      model: norm(values.model) as string | null,
      cpu_model: norm(values.cpu_model) as string | null,
      asset_tag: norm(values.asset_tag) as string | null,
      ip_inband: norm(values.ip_inband) as string | null,
      bmc_ip: norm(values.bmc_ip) as string | null,
      u_start: values.u_start ?? null,
      u_end: values.u_end ?? null,
      status: values.status ?? null,
      remark: norm(values.remark) as string | null,
    }
    setSubmitting(true)
    try {
      const updated = await updateAsset(asset.id, payload)
      message.success('已保存')
      onSaved(updated)
      onClose()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={asset !== null}
      title={asset ? `编辑设备 ${asset.model || asset.sn || '#' + asset.id}` : ''}
      okText="保存"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={onSubmit}
      onCancel={onClose}
      destroyOnClose
      forceRender
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="SN" name="sn" extra={asset ? sourceHint(asset, 'sn') : undefined}>
          <Input placeholder="整机序列号" />
        </Form.Item>
        <Form.Item label="型号" name="model">
          <Input placeholder="型号" />
        </Form.Item>
        <Form.Item label="CPU 型号" name="cpu_model" extra={asset ? sourceHint(asset, 'cpu_model') : undefined}>
          <Input placeholder="CPU 型号" />
        </Form.Item>
        <Form.Item label="资产标签" name="asset_tag">
          <Input placeholder="资产标签" />
        </Form.Item>
        <Form.Item label="带内 IP" name="ip_inband" extra={asset ? sourceHint(asset, 'ip_inband') : undefined}>
          <Input placeholder="带内 IP" />
        </Form.Item>
        <Form.Item label="BMC IP" name="bmc_ip" extra={asset ? sourceHint(asset, 'bmc_ip') : undefined}>
          <Input placeholder="BMC / 管理口 IP" />
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
        <Form.Item label="状态" name="status">
          <Select options={statusOptions} />
        </Form.Item>
        <Form.Item label="备注" name="remark">
          <Input.TextArea rows={2} placeholder="备注" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
