import { useEffect, useState } from 'react'
import { Form, Input, InputNumber, Modal, Select, message } from 'antd'
import { getErrorMessage } from '../api/client'
import { createComponent, updateComponent } from '../api'
import type { Component } from '../api/types'

// 部件类别已知取值（导入 7 类 + PRD 数量管理项）；完整字典 seed 另属 backlog。
const CATEGORY_OPTIONS = [
  '硬盘',
  '内存',
  '主板',
  '光模块',
  'RAID',
  '网卡',
  'BMC插卡',
  'CPU',
  '线缆',
  '风扇板',
].map((c) => ({ value: c, label: c }))

function norm(v: string | null | undefined): string | null {
  if (v === '' || v === undefined) return null
  return v
}

interface Props {
  assetId: number
  component: Component | null // null = 新增
  onClose: () => void
  onSaved: () => void
}

export default function ComponentFormModal({ assetId, component, onClose, onSaved }: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const isEdit = component !== null

  useEffect(() => {
    if (component) {
      form.setFieldsValue({
        category: component.category,
        sn: component.sn ?? '',
        model: component.model ?? '',
        qty: component.qty,
        remark: component.remark ?? '',
      })
    } else {
      form.setFieldsValue({ category: undefined, sn: '', model: '', qty: 1, remark: '' })
    }
  }, [component, form])

  const onSubmit = async () => {
    const values = await form.validateFields()
    const body = {
      category: values.category,
      sn: norm(values.sn),
      model: norm(values.model),
      qty: values.qty ?? 1,
      remark: norm(values.remark),
    }
    setSubmitting(true)
    try {
      if (isEdit) {
        await updateComponent(component.id, body)
      } else {
        await createComponent({ asset_id: assetId, ...body })
      }
      message.success(isEdit ? '已保存' : '已添加')
      onSaved()
      onClose()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open
      title={isEdit ? '编辑部件' : '添加部件'}
      okText="保存"
      cancelText="取消"
      confirmLoading={submitting}
      onOk={onSubmit}
      onCancel={onClose}
      destroyOnClose
      forceRender
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="物料类型" name="category" rules={[{ required: true, message: '请选择物料类型' }]}>
          <Select options={CATEGORY_OPTIONS} placeholder="选择物料类型" allowClear />
        </Form.Item>
        <Form.Item label="SN" name="sn">
          <Input placeholder="部件序列号（无 SN 可留空）" />
        </Form.Item>
        <Form.Item label="型号" name="model">
          <Input placeholder="型号" />
        </Form.Item>
        <Form.Item label="数量" name="qty" rules={[{ required: true, message: '请输入数量' }]}>
          <InputNumber min={1} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item label="备注" name="remark">
          <Input.TextArea rows={2} placeholder="备注" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
