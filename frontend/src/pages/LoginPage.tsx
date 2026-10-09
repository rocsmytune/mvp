import { useState } from 'react'
import { Alert, Button, Card, Form, Input, Select, Typography } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import { api, getErrorMessage } from '../api/client'
import { APP_VERSION } from '../constants'
import type { UserInfo } from '../api/types'

interface Props {
  onLogin: (user: UserInfo) => void
}

type Mode = 'login' | 'register'

export default function LoginPage({ onLogin }: Props) {
  const [mode, setMode] = useState<Mode>('login')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [registerForm] = Form.useForm()

  const switchMode = (m: Mode) => {
    setError(null)
    setNotice(null)
    setMode(m)
  }

  const onLoginFinish = async (values: { employee_no: string; password: string }) => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await api.post('/auth/login', values)
      localStorage.setItem('token', res.data.access_token)
      onLogin(res.data.user)
    } catch (e) {
      setError(getErrorMessage(e, '登录失败：工号或密码错误'))
    } finally {
      setSubmitting(false)
    }
  }

  const onRegisterFinish = async (values: {
    name: string
    employee_no: string
    password: string
    role: string
  }) => {
    setError(null)
    setNotice(null)
    setSubmitting(true)
    try {
      await api.post('/auth/register', {
        employee_no: values.employee_no,
        name: values.name,
        password: values.password,
        role: values.role,
      })
      registerForm.resetFields()
      setMode('login')
      setNotice(
        values.role === 'cabinet_owner'
          ? '注册成功，请登录。柜主需管理员在「机柜管理」指派柜主后才有对应机柜权限。'
          : '注册成功，请登录。',
      )
    } catch (e) {
      setError(getErrorMessage(e, '注册失败'))
    } finally {
      setSubmitting(false)
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
      <Card style={{ width: 420 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <DatabaseOutlined style={{ fontSize: 40, color: '#0958d9' }} />
          <Typography.Title level={3} style={{ marginTop: 12, marginBottom: 0 }}>
            Kunpeng KNOW
          </Typography.Title>
          <Typography.Text type="secondary">机柜物料管理平台</Typography.Text>
        </div>
        {notice && <Alert type="success" message={notice} style={{ marginBottom: 16 }} showIcon />}
        {error && <Alert type="error" message={error} style={{ marginBottom: 16 }} showIcon />}

        {mode === 'login' ? (
          <>
            <Form onFinish={onLoginFinish} layout="vertical">
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
                <Button type="primary" htmlType="submit" block loading={submitting}>
                  登录
                </Button>
              </Form.Item>
            </Form>
            <div style={{ textAlign: 'center', marginBottom: 8 }}>
              <Button type="link" onClick={() => switchMode('register')}>
                没有账号？注册成员 / 柜主
              </Button>
            </div>
          </>
        ) : (
          <>
            <Form form={registerForm} onFinish={onRegisterFinish} layout="vertical">
              <Form.Item
                name="name"
                label="姓名"
                rules={[{ required: true, message: '请输入姓名' }]}
              >
                <Input placeholder="姓名" autoFocus />
              </Form.Item>
              <Form.Item
                name="employee_no"
                label="工号"
                rules={[{ required: true, message: '请输入工号' }]}
              >
                <Input placeholder="工号" />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="密码" />
              </Form.Item>
              <Form.Item
                name="confirm"
                label="确认密码"
                dependencies={['password']}
                rules={[
                  { required: true, message: '请再次输入密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('password') === value) {
                        return Promise.resolve()
                      }
                      return Promise.reject(new Error('两次输入的密码不一致'))
                    },
                  }),
                ]}
              >
                <Input.Password placeholder="确认密码" />
              </Form.Item>
              <Form.Item
                name="role"
                label="角色"
                initialValue="member"
                rules={[{ required: true, message: '请选择角色' }]}
              >
                <Select
                  options={[
                    { value: 'member', label: '成员' },
                    { value: 'cabinet_owner', label: '柜主（注册后需管理员指派柜主）' },
                  ]}
                />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" block loading={submitting}>
                  注册
                </Button>
              </Form.Item>
            </Form>
            <div style={{ textAlign: 'center', marginBottom: 8 }}>
              <Button type="link" onClick={() => switchMode('login')}>
                已有账号？去登录
              </Button>
            </div>
          </>
        )}

        <Button block disabled>
          SSO 登录（预留）
        </Button>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            Kunpeng KNOW · v{APP_VERSION}
          </Typography.Text>
        </div>
      </Card>
    </div>
  )
}
