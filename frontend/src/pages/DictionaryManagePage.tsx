import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Form, Input, InputNumber, Modal, Space, Table, Tabs, Tag, Tooltip, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { getErrorMessage } from '../api/client'
import { createDictionary, deleteDictionary, fetchDictionaries, fetchDictionaryUsage, updateDictionary } from '../api'
import { DICT_KIND_LABEL } from '../constants'
import { uText } from '../lib/format'
import type { Dictionary, DictionaryUsage } from '../api/types'

interface DictFormValues {
  code?: string
  label?: string
  sort_no?: number
}

export default function DictionaryManagePage() {
  const [dicts, setDicts] = useState<Dictionary[]>([])
  const [loading, setLoading] = useState(true)
  const [activeKind, setActiveKind] = useState<string>('component_category')
  const [editing, setEditing] = useState<Dictionary | null>(null)
  const [creatingKind, setCreatingKind] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [usageDict, setUsageDict] = useState<Dictionary | null>(null)
  const [usage, setUsage] = useState<DictionaryUsage[]>([])
  const [usageLoading, setUsageLoading] = useState(false)
  const [form] = Form.useForm<DictFormValues>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setDicts(await fetchDictionaries())
    } catch (e) {
      message.error(getErrorMessage(e, '加载字典失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const modalOpen = editing !== null || creatingKind !== null

  function closeForm() {
    setEditing(null)
    setCreatingKind(null)
    form.resetFields()
  }

  async function onSubmit(values: DictFormValues) {
    setSaving(true)
    try {
      if (editing) {
        await updateDictionary(editing.id, {
          code: values.code ?? '',
          label: values.label ?? '',
          sort_no: values.sort_no ?? 0,
        })
        message.success('已保存')
      } else if (creatingKind) {
        await createDictionary({
          kind: creatingKind,
          code: values.code ?? '',
          label: values.label ?? '',
          sort_no: values.sort_no ?? 0,
        })
        message.success('已新增')
      }
      closeForm()
      void load()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  async function openUsage(d: Dictionary) {
    setUsageDict(d)
    setUsage([])
    setUsageLoading(true)
    try {
      setUsage(await fetchDictionaryUsage(d.id))
    } catch (e) {
      message.error(getErrorMessage(e, '加载使用位置失败'))
    } finally {
      setUsageLoading(false)
    }
  }

  function confirmDelete(d: Dictionary) {
    Modal.confirm({
      title: `删除字典值「${d.label}」？`,
      content: '仅未被使用的值可删除；删除后不可恢复。',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteDictionary(d.id)
          message.success('已删除')
          void load()
        } catch (e) {
          message.error(getErrorMessage(e, '删除失败'))
        }
      },
    })
  }

  const columns: TableColumnsType<Dictionary> = [
    { title: '显示名', dataIndex: 'label', width: 160 },
    { title: '编码', dataIndex: 'code', width: 160 },
    { title: '排序', dataIndex: 'sort_no', width: 70 },
    {
      title: '使用数',
      dataIndex: 'usage_count',
      width: 90,
      render: (v: number) => <Tag color={v > 0 ? 'blue' : 'default'}>{v}</Tag>,
    },
    {
      title: '操作',
      width: 200,
      render: (_, d) => (
        <Space size={0}>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setEditing(d)
              form.setFieldsValue({ code: d.code, label: d.label, sort_no: d.sort_no })
            }}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            disabled={d.usage_count === 0}
            onClick={() => openUsage(d)}
          >
            查看位置
          </Button>
          {d.usage_count === 0 ? (
            <Button type="link" size="small" danger onClick={() => confirmDelete(d)}>
              删除
            </Button>
          ) : (
            <Tooltip title={`正被 ${d.usage_count} 处使用，无法删除`}>
              <Button type="link" size="small" danger disabled>
                删除
              </Button>
            </Tooltip>
          )}
        </Space>
      ),
    },
  ]

  const usageColumns: TableColumnsType<DictionaryUsage> = [
    {
      title: '类型',
      dataIndex: 'target_type',
      width: 70,
      render: (v: string) => (v === 'asset' ? '整机' : '部件'),
    },
    { title: 'SN', dataIndex: 'sn', width: 140, render: (v) => v ?? '—' },
    { title: '父资产SN', dataIndex: 'asset_sn', width: 140, render: (v) => v ?? '—' },
    { title: '机柜', dataIndex: 'cabinet_name', render: (v) => v ?? '—' },
    { title: 'U位', width: 80, render: (_, u) => uText(u.u_start, u.u_end) },
  ]

  function renderKindTable(kind: string) {
    const rows = dicts.filter((d) => d.kind === kind)
    return (
      <Table
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        pagination={false}
      />
    )
  }

  return (
    <Card
      title="字典管理"
      extra={
        <span style={{ color: '#999', fontSize: 12 }}>
          字典值供下拉框使用；禁止删除，删除前可先「查看位置」。
        </span>
      }
    >
      <Tabs
        activeKey={activeKind}
        onChange={setActiveKind}
        tabBarExtraContent={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null)
              form.resetFields()
              setCreatingKind(activeKind)
            }}
          >
            新增字典项
          </Button>
        }
        items={Object.keys(DICT_KIND_LABEL).map((kind) => ({
          key: kind,
          label: DICT_KIND_LABEL[kind],
          children: renderKindTable(kind),
        }))}
      />

      <Modal
        title={editing ? '编辑字典项' : `新增字典项（${DICT_KIND_LABEL[creatingKind ?? ''] ?? ''}）`}
        open={modalOpen}
        onOk={() => form.submit()}
        onCancel={closeForm}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
      >
        <Form form={form} layout="vertical" onFinish={onSubmit} requiredMark>
          <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入编码' }]}>
            <Input placeholder="如 in_use / 硬盘，同类别内唯一" />
          </Form.Item>
          <Form.Item name="label" label="显示名" rules={[{ required: true, message: '请输入显示名' }]}>
            <Input placeholder="下拉框展示的文字" />
          </Form.Item>
          <Form.Item name="sort_no" label="排序" extra="数字越小越靠前">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`「${usageDict?.label ?? ''}」使用位置（${usage.length}）`}
        open={usageDict !== null}
        footer={null}
        onCancel={() => setUsageDict(null)}
        width={720}
      >
        <Table
          rowKey={(_, i) => String(i)}
          columns={usageColumns}
          dataSource={usage}
          loading={usageLoading}
          size="small"
          pagination={false}
        />
      </Modal>
    </Card>
  )
}
