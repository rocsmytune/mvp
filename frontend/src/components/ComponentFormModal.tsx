import { useEffect, useState } from 'react'
import { Form, Input, Modal, Select, message } from 'antd'
import { getErrorMessage } from '../api/client'
import { createComponent, fetchDictionaries, updateComponent } from '../api'
import type { Component } from '../api/types'

// 部件类别回退取值（字典接口拉取失败时兜底）。
const FALLBACK_CATEGORIES = ['硬盘', '内存', '主板', '光模块', 'RAID', '网卡', 'BMC插卡', 'CPU', '线缆', '风扇板']

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
  const [categoryOptions, setCategoryOptions] = useState<{ value: string; label: string }[]>(
    FALLBACK_CATEGORIES.map((c) => ({ value: c, label: c })),
  )
  const isEdit = component !== null

  useEffect(() => {
    fetchDictionaries('component_category')
      .then((dicts) => {
        if (dicts.length > 0) {
          setCategoryOptions(dicts.map((d) => ({ value: d.code, label: d.label })))
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (component) {
      form.setFieldsValue({
        category: component.category,
        sn: component.sn ?? '',
        model: component.model ?? '',
        name: component.name ?? '',
        material_code: component.material_code ?? '',
        // 已关联工号时还原「工号 姓名」，否则回显裸姓名（再保存不会丢 holder_id 关联）
        holder_name: component.holder_employee_no
          ? `${component.holder_employee_no} ${component.holder_name ?? ''}`.trim()
          : (component.holder_name ?? ''),
        remark: component.remark ?? '',
      })
    } else {
      form.setFieldsValue({ category: undefined, sn: '', model: '', name: '', material_code: '', holder_name: '', remark: '' })
    }
  }, [component, form])

  const onSubmit = async () => {
    const values = await form.validateFields()
    const body = {
      category: values.category,
      sn: norm(values.sn),
      model: norm(values.model),
      name: norm(values.name),
      material_code: norm(values.material_code),
      holder_name: norm(values.holder_name),
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
          <Select options={categoryOptions} placeholder="选择物料类型" allowClear />
        </Form.Item>
        <Form.Item label="SN" name="sn">
          <Input placeholder="部件序列号（无 SN 可留空）" />
        </Form.Item>
        <Form.Item label="型号" name="model">
          <Input placeholder="型号" />
        </Form.Item>
        <Form.Item label="名称" name="name">
          <Input placeholder="物料名称" />
        </Form.Item>
        <Form.Item label="物料编码" name="material_code">
          <Input placeholder="物料编码" />
        </Form.Item>
        <Form.Item label="挂账人" name="holder_name">
          <Input placeholder="工号 姓名（可留空）" />
        </Form.Item>
        <Form.Item label="备注" name="remark">
          <Input.TextArea rows={2} placeholder="备注" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
