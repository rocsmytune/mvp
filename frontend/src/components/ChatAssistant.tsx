import { useEffect, useRef, useState } from 'react'
import {
  Button,
  Input,
  InputNumber,
  Modal,
  Space,
  Switch,
  Tag,
  Tabs,
  Typography,
  message,
} from 'antd'
import { RobotOutlined, SendOutlined, SettingOutlined } from '@ant-design/icons'
import {
  chatWithAssistant,
  fetchGlobalConfig,
  fetchPersonalConfig,
  testLlmConnection,
  updateGlobalConfig,
  updatePersonalConfig,
} from '../api'
import { getErrorMessage } from '../api/client'
import type { SearchResult, UserInfo } from '../api/types'

interface Msg {
  role: 'user' | 'assistant'
  text: string
  hits?: SearchResult[]
}

function locText(r: SearchResult): string {
  if (!r.cabinet_name) return '待整理池'
  const u =
    r.u_start == null ? '—' : r.u_start === r.u_end ? `${r.u_start}U` : `${r.u_start}-${r.u_end}U`
  return `${r.room_code ?? '—'} · ${r.cabinet_name} · ${u} · 柜主 ${r.owner_name ?? '未指派'}`
}

function idText(r: SearchResult): string {
  if (r.kind === 'asset') return r.asset_sn || r.asset_tag || r.model || `#${r.asset_id}`
  return r.component_sn || r.component_name || `#${r.component_id}`
}

// ---------- 个人配置表单 ----------

function PersonalConfigForm({ onSaved }: { onSaved?: () => void }) {
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [masked, setMasked] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    fetchPersonalConfig()
      .then((c) => {
        setBaseUrl(c.base_url ?? '')
        setModel(c.model ?? '')
        setEnabled(c.enabled)
        setMasked(c.api_key_masked)
      })
      .catch(() => {})
  }, [])

  const doTest = async () => {
    if (!baseUrl.trim()) {
      message.warning('请先填写 Base URL')
      return
    }
    setTesting(true)
    try {
      const r = await testLlmConnection({
        base_url: baseUrl.trim(),
        api_key: apiKey || undefined,
        model: model.trim() || undefined,
      })
      if (r.ok) message.success(r.message)
      else message.error(r.message)
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        base_url: baseUrl.trim() || null,
        model: model.trim() || null,
        enabled,
      }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      const c = await updatePersonalConfig(payload)
      setMasked(c.api_key_masked)
      setApiKey('')
      message.success('已保存')
      onSaved?.()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const clearKey = async () => {
    setLoading(true)
    try {
      const c = await updatePersonalConfig({ api_key: '' })
      setMasked(c.api_key_masked)
      setApiKey('')
      message.success('已清除密钥')
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          填写你自己的 API（覆盖全局默认）。留空则使用平台默认 API，并按默认 API 的每日 token 额度计。
        </Typography.Text>
      </div>
      <div>
        <Typography.Text>Base URL</Typography.Text>
        <Input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://your-llm.example.com/v1"
        />
      </div>
      <div>
        <Typography.Text>模型</Typography.Text>
        <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="模型名，如 glm-4" />
      </div>
      <div>
        <Typography.Text>API Key</Typography.Text>
        <Input.Password
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={masked ? `已配置（${masked}），留空不修改` : '未配置'}
        />
        {masked && (
          <Button type="link" size="small" onClick={clearKey} style={{ paddingLeft: 0 }}>
            清除密钥
          </Button>
        )}
      </div>
      <div>
        <Typography.Text>启用个人配置</Typography.Text>{' '}
        <Switch checked={enabled} onChange={setEnabled} />
      </div>
      <Space>
        <Button onClick={doTest} loading={testing}>
          测试连通
        </Button>
        <Button type="primary" onClick={save} loading={loading}>
          保存
        </Button>
      </Space>
    </div>
  )
}

// ---------- 全局配置表单（仅系统管理员） ----------

function GlobalConfigForm({ onSaved }: { onSaved?: () => void }) {
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [quota, setQuota] = useState<number>(50000)
  const [masked, setMasked] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    fetchGlobalConfig()
      .then((c) => {
        setBaseUrl(c.base_url ?? '')
        setModel(c.model ?? '')
        setQuota(c.daily_token_quota)
        setMasked(c.api_key_masked)
      })
      .catch(() => {})
  }, [])

  const doTest = async () => {
    if (!baseUrl.trim()) {
      message.warning('请先填写 Base URL')
      return
    }
    setTesting(true)
    try {
      const r = await testLlmConnection({
        base_url: baseUrl.trim(),
        api_key: apiKey || undefined,
        model: model.trim() || undefined,
      })
      if (r.ok) message.success(r.message)
      else message.error(r.message)
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setTesting(false)
    }
  }

  const save = async () => {
    setLoading(true)
    try {
      const payload: Record<string, unknown> = {
        base_url: baseUrl.trim() || null,
        model: model.trim() || null,
        daily_token_quota: quota,
      }
      if (apiKey.trim()) payload.api_key = apiKey.trim()
      const c = await updateGlobalConfig(payload)
      setMasked(c.api_key_masked)
      setApiKey('')
      message.success('已保存')
      onSaved?.()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  const clearKey = async () => {
    setLoading(true)
    try {
      const c = await updateGlobalConfig({ api_key: '' })
      setMasked(c.api_key_masked)
      setApiKey('')
      message.success('已清除密钥')
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          平台默认 API：未配置个人 API 的用户走此配置，并按「每日 token 额度」累计用量。
        </Typography.Text>
      </div>
      <div>
        <Typography.Text>Base URL</Typography.Text>
        <Input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://your-llm.example.com/v1"
        />
      </div>
      <div>
        <Typography.Text>模型</Typography.Text>
        <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="模型名" />
      </div>
      <div>
        <Typography.Text>API Key</Typography.Text>
        <Input.Password
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={masked ? `已配置（${masked}），留空不修改` : '未配置'}
        />
        {masked && (
          <Button type="link" size="small" onClick={clearKey} style={{ paddingLeft: 0 }}>
            清除密钥
          </Button>
        )}
      </div>
      <div>
        <Typography.Text>每日 token 额度（每用户）</Typography.Text>{' '}
        <InputNumber min={0} max={10000000} value={quota} onChange={(v) => setQuota(v ?? 0)} />
      </div>
      <Space>
        <Button onClick={doTest} loading={testing}>
          测试连通
        </Button>
        <Button type="primary" onClick={save} loading={loading}>
          保存
        </Button>
      </Space>
    </div>
  )
}

// ---------- 主组件 ----------

export default function ChatAssistant({
  user,
  onNavigate,
}: {
  user: UserInfo
  onNavigate: (cabinetId: number, assetId: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [hover, setHover] = useState(false)
  const [configOpen, setConfigOpen] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text }])
    setLoading(true)
    try {
      const res = await chatWithAssistant(text)
      setMessages((m) => [...m, { role: 'assistant', text: res.reply, hits: res.hits }])
    } catch (e) {
      setMessages((m) => [...m, { role: 'assistant', text: getErrorMessage(e, '服务异常，请稍后重试') }])
    } finally {
      setLoading(false)
    }
  }

  const jump = (h: SearchResult) => {
    if (h.cabinet_id == null) return
    onNavigate(h.cabinet_id, h.asset_id)
    setOpen(false)
  }

  const tabs = [
    { key: 'personal', label: '我的配置', children: <PersonalConfigForm /> },
    ...(user.role === 'system_admin'
      ? [{ key: 'global', label: '全局默认', children: <GlobalConfigForm /> }]
      : []),
  ]

  return (
    <>
      {/* 右下角偏透明悬浮球，点击展开对话框 */}
      <div style={{ position: 'fixed', bottom: 28, right: 28, zIndex: 1000 }}>
        <Button
          type="primary"
          shape="circle"
          icon={<RobotOutlined style={{ fontSize: 22 }} />}
          onClick={() => setOpen(true)}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          style={{
            width: 54,
            height: 54,
            opacity: hover ? 1 : 0.6,
            boxShadow: hover ? '0 6px 16px rgba(0,0,0,0.28)' : '0 3px 10px rgba(0,0,0,0.15)',
            transition: 'opacity 0.2s, box-shadow 0.2s',
          }}
        />
      </div>

      <Modal
        open={open}
        onCancel={() => setOpen(false)}
        footer={null}
        width={400}
        title={
          <Space>
            <span>智能助手</span>
            <Button size="small" type="text" icon={<SettingOutlined />} onClick={() => setConfigOpen(true)}>
              配置
            </Button>
          </Space>
        }
      >
        <div
          ref={listRef}
          style={{ height: 420, overflowY: 'auto', paddingRight: 4, marginBottom: 12 }}
        >
          {messages.length === 0 && (
            <div style={{ color: '#8c8c8c', paddingTop: 60, textAlign: 'center' }}>
              可以问我：设备/部件在哪个机柜、某机柜有哪些设备、物料怎么导入、盘点统计等。
            </div>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              style={{
                display: 'flex',
                justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 10,
              }}
            >
              <div style={{ maxWidth: '85%' }}>
                <div
                  style={{
                    background: m.role === 'user' ? '#1677ff' : '#f0f0f0',
                    color: m.role === 'user' ? '#fff' : 'rgba(0,0,0,0.88)',
                    padding: '8px 12px',
                    borderRadius: 8,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {m.text}
                </div>
                {m.hits && m.hits.length > 0 && (
                  <div style={{ marginTop: 6 }}>
                    {m.hits.map((h, j) => (
                      <div
                        key={j}
                        onClick={() => jump(h)}
                        style={{
                          cursor: h.cabinet_id == null ? 'default' : 'pointer',
                          padding: '6px 8px',
                          border: '1px solid #f0f0f0',
                          borderRadius: 6,
                          marginBottom: 4,
                          background: '#fafafa',
                        }}
                      >
                        <div>
                          <Tag color={h.kind === 'asset' ? 'blue' : 'purple'} style={{ marginRight: 4 }}>
                            {h.kind === 'asset' ? '整机' : `部件·${h.component_category ?? ''}`}
                          </Tag>
                          <span style={{ fontWeight: 500 }}>{idText(h)}</span>
                        </div>
                        <div style={{ color: '#8c8c8c', fontSize: 12 }}>{locText(h)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && <div style={{ textAlign: 'center', color: '#8c8c8c' }}>思考中…</div>}
        </div>
        <Space.Compact style={{ width: '100%' }}>
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={send}
            placeholder="问点什么…（Enter 发送）"
          />
          <Button type="primary" icon={<SendOutlined />} onClick={send} loading={loading} />
        </Space.Compact>
      </Modal>

      <Modal
        open={configOpen}
        onCancel={() => setConfigOpen(false)}
        footer={null}
        width={480}
        title="智能助手配置"
      >
        <Tabs items={tabs} />
      </Modal>
    </>
  )
}
