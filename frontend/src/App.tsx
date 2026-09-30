import { useEffect, useState } from 'react'
import { Layout, Result, Spin, Typography } from 'antd'
import axios from 'axios'

type Status = 'loading' | 'ok' | 'error'

export default function App() {
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    axios
      .get('/health')
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Layout.Content style={{ padding: 48 }}>
        <Typography.Title level={2}>机柜物料管理平台</Typography.Title>
        {status === 'loading' && (
          <Spin tip="检查后端连接…">
            <div style={{ height: 120 }} />
          </Spin>
        )}
        {status === 'ok' && (
          <Result
            status="success"
            title="骨架已就绪"
            subTitle="前端 ↔ 后端 ↔ 数据库 连接正常"
          />
        )}
        {status === 'error' && (
          <Result
            status="error"
            title="后端连接失败"
            subTitle="请确认 backend 容器已启动，后端地址见 vite.config.ts 的代理配置"
          />
        )}
      </Layout.Content>
    </Layout>
  )
}
