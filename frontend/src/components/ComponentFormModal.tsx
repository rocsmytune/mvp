import { useEffect, useState } from 'react'
import { Form, Input, Modal, Select, message } from 'antd'
import { getErrorMessage } from '../api/client'
import { createComponent, fetchAssetPage, fetchDictionaries, updateComponent } from '../api'
import type { Asset, Component } from '../api/types'

// 部件类别回退取值（字典接口拉取失败时兜底）。
const FALLBACK_CATEGORIES = ['硬盘', '内存', '主板', '光模块', 'RAID', '网卡', 'BMC插卡', 'CPU', '线缆', '风扇板']

function norm(v: string | null | undefined): string | null {
  if (v === '' || v === undefined) return null
  return v
}

// 「所在整机」索引：以 BMC IP + 整机SN 标识，缺省依次回退。
function assetIndexLabel(bmc: string | null | undefined, sn: string | null | undefined, model: string | null | undefined, id: number): string {
  if (bmc && sn) return `${bmc} · ${sn}`
  return bmc || sn || model || `#${id}`
}

function compAssetLabel(c: Component): string {
  return assetIndexLabel(c.asset_bmc_ip, c.asset_sn, c.asset_model, c.asset_id)
}

interface Props {
  assetId: number
  component: Component | null // null = 新增
  movable?: boolean // 列表页编辑时可改「所在整机」
  onClose: () => void
  onSaved: () => void
}

export default function ComponentFormModal({ assetId, component, movable, onClose, onSaved }: Props) {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [categoryOptions, setCategoryOptions] = useState<{ value: string; label: string }[]>(
    FALLBACK_CATEGORIES.map((c) => ({ value: c, label: c })),
  )
  const isEdit = component !== null

  // 「所在整机」远程搜索（movable 编辑时用）：按 SN / IP / 型号 定位目标整机。
  const initialOption = component
    ? { value: component.asset_id, label: compAssetLabel(component) }
    : null
  const [assetOptions, setAssetOptions] = useState<{ value: number; label: string }[]>(
    initialOption ? [initialOption] : [],
  )
  const [assetSearching, setAssetSearching] = useState(false)

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
        asset_id: component.asset_id,
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

  function searchAssets(kw: string) {
    const q = kw.trim()
    if (!q) {
      setAssetOptions(initialOption ? [initialOption] : [])
      return
    }
    setAssetSearching(true)
    fetchAssetPage({ q, limit: 50 })
      .then((res) => {
        const opts = res.items.map((a: Asset) => ({
          value: a.id,
          label: assetIndexLabel(a.bmc_ip, a.sn, a.model, a.id),
        }))
        // 当前所在整机始终可见，避免选中项脱离选项列表。
        if (initialOption && !opts.some((o) => o.value === initialOption.value)) {
          opts.unshift(initialOption)
        }
        setAssetOptions(opts)
      })
      .catch(() => setAssetOptions(initialOption ? [initialOption] : []))
      .finally(() => setAssetSearching(false))
  }

  const onSubmit = async () => {
    const values = await form.validateFields()
    const fields = {
      category: values.category as string,
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
        await updateComponent(component.id, {
          ...fields,
          ...(movable ? { asset_id: values.asset_id as number } : {}),
        })
      } else {
        await createComponent({ asset_id: assetId, ...fields })
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
        {isEdit && movable && (
          <Form.Item
            label="所在整机"
            name="asset_id"
            rules={[{ required: true, message: '请选择所在整机' }]}
          >
            <Select
              showSearch
              filterOption={false}
              onSearch={searchAssets}
              loading={assetSearching}
              options={assetOptions}
              placeholder="搜索 BMC IP / 整机SN 定位整机"
              notFoundContent={assetSearching ? '搜索中…' : '无匹配整机'}
            />
          </Form.Item>
        )}
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
