import { useEffect, useState } from 'react'
import { Button, Layout, Menu, Space, Tag, Typography } from 'antd'
import { DatabaseOutlined } from '@ant-design/icons'
import { ROLE_LABEL, APP_VERSION } from './constants'
import { api } from './api/client'
import type { UserInfo } from './api/types'
import LoginPage from './pages/LoginPage'
import OverviewPage from './pages/OverviewPage'
import ImportCenterPage from './pages/ImportCenterPage'
import UserManagePage from './pages/UserManagePage'
import DictionaryManagePage from './pages/DictionaryManagePage'
import CabinetManagePage from './pages/CabinetManagePage'
import AssetListPage from './pages/AssetListPage'
import GlobalSearch from './components/GlobalSearch'

// 业务管理员（系统管理员 / 物料管理员）：具备物料/机柜/导入/导出权限。
const isBusinessAdmin = (role: string) => role === 'system_admin' || role === 'material_admin'

type PageKey = 'overview' | 'assets' | 'import' | 'users' | 'dictionaries' | 'cabinets'

export default function App() {
  const [user, setUser] = useState<UserInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState<PageKey>('overview')
  // 搜索命中后跳转目标：打开对应机柜抽屉并选中该设备。
  const [focus, setFocus] = useState<{ cabinetId: number; assetId: number } | null>(null)

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

  const handleSearchNavigate = (cabinetId: number, assetId: number) => {
    setPage('overview')
    setFocus({ cabinetId, assetId })
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
    { key: 'assets', label: '设备物料' },
    ...(canImport ? [{ key: 'import', label: '导入中心' }] : []),
    ...(isBusinessAdmin(user.role) ? [{ key: 'cabinets', label: '机柜管理' }] : []),
    ...(user.role === 'system_admin' ? [{ key: 'users', label: '用户管理' }] : []),
    ...(user.role === 'system_admin' ? [{ key: 'dictionaries', label: '字典管理' }] : []),
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          paddingInline: 24,
        }}
      >
        <Space size={8} style={{ flexShrink: 0 }}>
          <DatabaseOutlined style={{ color: '#fff', fontSize: 20 }} />
          <Typography.Title level={4} style={{ color: '#fff', margin: 0, whiteSpace: 'nowrap' }}>
            Kunpeng KNOW
          </Typography.Title>
          <Typography.Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 12, whiteSpace: 'nowrap' }}>
            v{APP_VERSION}
          </Typography.Text>
        </Space>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[page]}
          onClick={({ key }) => setPage(key as PageKey)}
          items={menuItems}
          style={{ flex: 1, minWidth: 0, background: 'transparent', borderBottom: 'none' }}
        />
        <GlobalSearch onNavigate={handleSearchNavigate} />
        <Space style={{ flexShrink: 0 }}>
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
        {page === 'assets' ? (
          <AssetListPage user={user} onNavigate={handleSearchNavigate} />
        ) : page === 'import' ? (
          <ImportCenterPage isAdmin={isBusinessAdmin(user.role)} />
        ) : page === 'users' ? (
          <UserManagePage />
        ) : page === 'dictionaries' ? (
          <DictionaryManagePage />
        ) : page === 'cabinets' ? (
          <CabinetManagePage />
        ) : (
          <OverviewPage
            user={user}
            focus={focus}
            onFocusHandled={() => setFocus(null)}
          />
        )}
      </Layout.Content>
    </Layout>
  )
}
