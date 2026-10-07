import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Form, Input, Modal, Select, Space, Switch, Table, Tag, message } from 'antd'
import type { TableColumnsType } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { getErrorMessage } from '../api/client'
import { createUser, fetchUsers, updateUser } from '../api'
import type { UserAdmin } from '../api/types'

const ROLE_LABEL: Record<string, string> = {
  system_admin: '系统管理员',
  material_admin: '物料管理员',
  cabinet_owner: '柜主',
  member: '成员',
}
const ROLE_COLOR: Record<string, string> = {
  system_admin: 'red',
  material_admin: 'geekblue',
  cabinet_owner: 'green',
  member: 'default',
}
const ROLE_OPTIONS = Object.keys(ROLE_LABEL).map((v) => ({ value: v, label: ROLE_LABEL[v] }))

interface UserFormValues {
  employee_no?: string
  name?: string
  role?: string
  password?: string
  active?: boolean
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN')
}

export default function UserManagePage() {
  const [users, setUsers] = useState<UserAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [role, setRole] = useState<string | undefined>(undefined)
  const [createOpen, setCreateOpen] = useState(false)
  const [editUser, setEditUser] = useState<UserAdmin | null>(null)
  const [saving, setSaving] = useState(false)
  const [createForm] = Form.useForm<UserFormValues>()
  const [editForm] = Form.useForm<UserFormValues>()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchUsers({ q: q || undefined, role })
      setUsers(res.items)
    } catch (e) {
      message.error(getErrorMessage(e, '加载用户失败'))
    } finally {
      setLoading(false)
    }
  }, [q, role])

  useEffect(() => {
    void load()
  }, [load])

  async function onCreate(values: UserFormValues) {
    setSaving(true)
    try {
      await createUser({
        employee_no: values.employee_no ?? '',
        name: values.name ?? '',
        role: values.role ?? 'member',
        password: values.password ?? '',
      })
      message.success('已创建')
      setCreateOpen(false)
      createForm.resetFields()
      void load()
    } catch (e) {
      message.error(getErrorMessage(e, '创建失败'))
    } finally {
      setSaving(false)
    }
  }

  async function onEdit(values: UserFormValues) {
    if (!editUser) return
    setSaving(true)
    try {
      const payload: Record<string, string | boolean> = {}
      if (values.name) payload.name = values.name
      if (values.role) payload.role = values.role
      if (values.password) payload.password = values.password
      if (values.active !== undefined) payload.active = values.active
      await updateUser(editUser.id, payload)
      message.success('已保存')
      setEditUser(null)
      void load()
    } catch (e) {
      message.error(getErrorMessage(e, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  async function toggleActive(u: UserAdmin, active: boolean) {
    try {
      await updateUser(u.id, { active })
      message.success(active ? '已启用' : '已停用')
      void load()
    } catch (e) {
      message.error(getErrorMessage(e, '操作失败'))
    }
  }

  const columns: TableColumnsType<UserAdmin> = [
    { title: '工号', dataIndex: 'employee_no', width: 120 },
    { title: '姓名', dataIndex: 'name', width: 140 },
    {
      title: '角色',
      dataIndex: 'role',
      width: 120,
      render: (v: string) => <Tag color={ROLE_COLOR[v] ?? 'default'}>{ROLE_LABEL[v] ?? v}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'active',
      width: 110,
      render: (v: boolean, u) => (
        <Switch
          checked={v}
          checkedChildren="启用"
          unCheckedChildren="停用"
          onChange={(checked) => toggleActive(u, checked)}
        />
      ),
    },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: (v: string) => fmtTime(v) },
    {
      title: '操作',
      width: 90,
      render: (_, u) => (
        <Button
          type="link"
          size="small"
          onClick={() => {
            setEditUser(u)
            editForm.setFieldsValue({ name: u.name, role: u.role, active: u.active })
          }}
        >
          编辑
        </Button>
      ),
    },
  ]

  return (
    <Card
      title="用户管理"
      extra={
        <Space wrap>
          <Input.Search
            placeholder="按工号/姓名搜索"
            allowClear
            style={{ width: 220 }}
            onSearch={(v) => setQ(v)}
            onChange={(e) => {
              if (!e.target.value) setQ('')
            }}
          />
          <Select
            placeholder="按角色筛选"
            allowClear
            style={{ width: 140 }}
            value={role}
            onChange={setRole}
            options={ROLE_OPTIONS}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新增用户
          </Button>
        </Space>
      }
    >
      <Table
        rowKey="id"
        columns={columns}
        dataSource={users}
        loading={loading}
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true }}
      />

      <Modal
        title="新增用户"
        open={createOpen}
        onOk={() => createForm.submit()}
        onCancel={() => setCreateOpen(false)}
        okText="创建"
        cancelText="取消"
        confirmLoading={saving}
      >
        <Form form={createForm} layout="vertical" onFinish={onCreate} requiredMark>
          <Form.Item name="employee_no" label="工号" rules={[{ required: true, message: '请输入工号' }]}>
            <Input placeholder="登录工号，全局唯一" />
          </Form.Item>
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={ROLE_OPTIONS} placeholder="选择角色" />
          </Form.Item>
          <Form.Item name="password" label="初始密码" rules={[{ required: true, message: '请输入初始密码' }]}>
            <Input.Password placeholder="初始密码" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`编辑用户 ${editUser?.employee_no ?? ''}`}
        open={editUser !== null}
        onOk={() => editForm.submit()}
        onCancel={() => setEditUser(null)}
        okText="保存"
        cancelText="取消"
        confirmLoading={saving}
      >
        <Form form={editForm} layout="vertical" onFinish={onEdit} requiredMark>
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="姓名" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={ROLE_OPTIONS} placeholder="选择角色" />
          </Form.Item>
          <Form.Item name="password" label="重置密码" extra="留空则不修改">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>
          <Form.Item name="active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
