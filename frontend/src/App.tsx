import { useEffect, useState } from 'react'
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import { api } from './api/client'
import type { UserInfo } from './api/types'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import ImportCenterPage from './pages/ImportCenterPage'

const ROLE_LABEL: Record<string, string> = {
  admin: '总管理员',
  cabinet_owner: '柜主',
  member: '普通成员',
}

type PageKey = 'overview' | 'import'

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState<PageKey>('overview')

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
    setPage('overview')
  }

  if (loading) {
    return <Layout style={{ minHeight: '100vh' }} />
  }

  if (!user) {
    return <LoginPage onLogin={setUser} />
  }

  // 前端按角色隐藏入口只是体验优化，真正权限由后端强制（成员调接口会 403）。
  const canImport = user.role !== 'member'
  const menuItems = [
    { key: 'overview', label: '机房总览' },
    ...(canImport ? [{ key: 'import', label: '导入中心' }] : []),
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#001529',
          paddingInline: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
          <Typography.Title level={4} style={{ color: '#fff', margin: 0, whiteSpace: 'nowrap' }}>
            机柜物料管理平台
          </Typography.Title>
          <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[page]}
            onClick={({ key }) => setPage(key as PageKey)}
            items={menuItems}
            style={{ minWidth: 240, background: 'transparent', borderBottom: 'none' }}
          />
        </div>
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
        {page === 'import' ? <ImportCenterPage isAdmin={user.role === 'admin'} /> : <OverviewPage user={user} />}
      </Layout.Content>
    </Layout>
  )
}
