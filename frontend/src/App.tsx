import { useEffect, useState } from 'react'
import { Alert, Button, Card, Form, Input, Layout, Space, Tag, Typography } from 'antd'
import { api } from './api/client'

interface UserInfo {
  employee_no: string
  name: string
  role: string
}

const ROLE_LABEL: Record<string, string> = {
  admin: '总管理员',
  cabinet_owner: '柜主',
  member: '普通成员',
}

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      setLoading(false)
      return
    }
    api
      .get<UserInfo>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const onLogin = async (values: { employee_no: string; password: string }) => {
    setError(null)
    try {
      const res = await api.post('/auth/login', values)
      localStorage.setItem('token', res.data.access_token)
      setUser(res.data.user)
    } catch {
      setError('登录失败：工号或密码错误')
    }
  }

  const onLogout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  if (loading) {
    return <Layout style={{ minHeight: '100vh' }} />
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Content style={{ padding: 48, maxWidth: 480, margin: '0 auto', width: '100%' }}>
        {user ? (
          <Card title="机柜物料管理平台">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Typography.Text>
                欢迎，{user.name}（{user.employee_no}）
              </Typography.Text>
              <Space>
                <Typography.Text>角色：</Typography.Text>
                <Tag color="blue">{ROLE_LABEL[user.role] ?? user.role}</Tag>
              </Space>
              <Button type="primary" onClick={onLogout}>
                退出登录
              </Button>
            </Space>
          </Card>
        ) : (
          <Card title="登录">
            {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}
            <Form onFinish={onLogin} layout="vertical">
              <Form.Item
                name="employee_no"
                label="工号"
                rules={[{ required: true, message: '请输入工号' }]}
              >
                <Input placeholder="工号" autoFocus />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="密码" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" block>
                  登录
                </Button>
              </Form.Item>
            </Form>
            <Button block disabled>
              SSO 登录（预留）
            </Button>
          </Card>
        )}
      </Layout.Content>
    </Layout>
  )
}
