import { useState } from 'react'
import { Alert, Button, Card, Form, Input } from 'antd'
import { api } from '../api/client'
import type { UserInfo } from '../api/types'

interface Props {
  onLogin: (user: UserInfo) => void
}

export default function LoginPage({ onLogin }: Props) {
  const [error, setError] = useState<string | null>(null)

  const onFinish = async (values: { employee_no: string; password: string }) => {
    setError(null)
    try {
      const res = await api.post('/auth/login', values)
      localStorage.setItem('token', res.data.access_token)
      onLogin(res.data.user)
    } catch {
      setError('登录失败：工号或密码错误')
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card title="机柜物料管理平台" style={{ width: 400 }}>
        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}
        <Form onFinish={onFinish} layout="vertical">
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
    </div>
  )
}
