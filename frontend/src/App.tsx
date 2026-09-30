import { useEffect, useState } from 'react'
import { Button, Layout, Space, Tag, Typography } from 'antd'
import { api } from './api/client'
import type { UserInfo } from './api/types'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'

const ROLE_LABEL: Record<string, string> = {
  admin: '总管理员',
  cabinet_owner: '柜主',
  member: '普通成员',
}

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }
    api
      .get<UserInfo>('/auth/me')
      .then((res) => setUser(res.data))
      .catch(() => localStorage.removeItem('token'))
      .finally(() => setLoading(false))
  }, [])

  const onLogout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  if (loading) {
    return <Layout style={{ minHeight: '100vh' }} />
  }

  if (!user) {
    return <LoginPage onLogin={setUser} />
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#001529',
        }}
      >
        <Typography.Title level={4} style={{ color: '#fff', margin: 0 }}>
          机柜物料管理平台
        </Typography.Title>
        <Space>
          <Typography.Text style={{ color: '#fff' }}>
            {user.name}（{user.employee_no}）
          </Typography.Text>
          <Tag color="blue">{ROLE_LABEL[user.role] ?? user.role}</Tag>
          <Button size="small" onClick={onLogout}>
            退出登录
          </Button>
        </Space>
      </Layout.Header>
      <Layout.Content style={{ padding: 24 }}>
        <OverviewPage />
      </Layout.Content>
    </Layout>
  )
}
