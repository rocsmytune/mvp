import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Empty,
  message,
  Modal,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  Upload,
} from 'antd'
import type { TableColumnsType, UploadProps } from 'antd'
import {
  CheckCircleFilled,
  CloseCircleFilled,
  CloudDownloadOutlined,
  DownloadOutlined,
  ExclamationCircleFilled,
  EyeOutlined,
  HistoryOutlined,
  InboxOutlined,
  PlusCircleOutlined,
  ReloadOutlined,
  SyncOutlined,
  WarningFilled,
} from '@ant-design/icons'
import { confirmImport, fetchExportSnapshot, fetchImportBatches, uploadImport } from '../api'
import type {
  ImportBatch,
  ImportConfirmResponse,
  ImportPreviewRow,
  ImportRow,
  ImportUploadResponse,
} from '../api/types'
import { downloadBackup, downloadImportTemplate, IMPORT_HEADERS, parseImportExcel } from '../lib/excel'

// 可服务性：状态「三层编码」——颜色 Tag + 图标 + 文字，不只依赖颜色（色弱友好）。
const ACTION_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  new: { label: '新增', color: 'success', icon: <PlusCircleOutlined /> },
  update: { label: '更新', color: 'processing', icon: <SyncOutlined /> },
  error: { label: '错误', color: 'error', icon: <CloseCircleFilled /> },
}

const RESULT_META: Record<string, { label: string; color: string }> = {
  created: { label: '已新增', color: 'success' },
  updated: { label: '已更新', color: 'processing' },
  skipped: { label: '已跳过', color: 'warning' },
}

const FIELD_LABEL: Record<string, string> = {
  asset_id: '机柜位置',
  sn: 'SN',
  name: '名称',
  material_code: '物料编码',
  remark: '备注',
  holder_id: '挂账人',
  holder_name: '挂账人',
}

const BATCH_STATUS_META: Record<string, { label: string; color: string }> = {
  previewed: { label: '待确认', color: 'warning' },
  committed: { label: '已入库', color: 'success' },
}

type Phase = 'idle' | 'preview' | 'done'

function fmt(value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return value
}

function uText(row: { u_start: number | null; u_end: number | null }): string {
  if (row.u_start === null || row.u_end === null) return '—'
  return row.u_start === row.u_end ? `${row.u_start}U` : `${row.u_start}-${row.u_end}U`
}

function fmtTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('zh-CN')
}

export default function ImportCenterPage({ isAdmin }: { isAdmin: boolean }) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [uploading, setUploading] = useState(false)
  const [preview, setPreview] = useState<ImportUploadResponse | null>(null)
  const [parseWarnings, setParseWarnings] = useState<string[]>([])
  const [result, setResult] = useState<ImportConfirmResponse | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [exporting, setExporting] = useState(false)

  const [batches, setBatches] = useState<ImportBatch[]>([])
  const [batchesLoading, setBatchesLoading] = useState(true)
  const [detailBatch, setDetailBatch] = useState<ImportBatch | null>(null)

  const refreshBatches = useCallback(async () => {
    try {
      const res = await fetchImportBatches()
      setBatches(res.items)
    } catch {
      // 历史加载失败不打断主流程
    } finally {
      setBatchesLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshBatches()
  }, [refreshBatches])

  async function handleFile(file: File) {
    setUploading(true)
    setParseWarnings([])
    try {
      const buf = await file.arrayBuffer()
      const { rows, warnings } = parseImportExcel(buf)
      setParseWarnings(warnings)
      const prev = await uploadImport(rows, file.name)
      setPreview(prev)
      setResult(null)
      setPhase('preview')
      void refreshBatches()
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail ?? (e instanceof Error ? e.message : '解析失败，请检查文件格式'))
    } finally {
      setUploading(false)
    }
  }

  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    void handleFile(file)
    return false // 阻止默认上传，自行解析 + 调预览接口
  }

  function reset() {
    setPhase('idle')
    setPreview(null)
    setResult(null)
    setParseWarnings([])
  }

  async function doConfirm() {
    if (!preview) return
    setConfirming(true)
    try {
      const res = await confirmImport(preview.batch_id)
      setResult(res)
      setPhase('done')
      void refreshBatches()
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail ? `入库失败：${detail}` : '入库失败，请重试')
    } finally {
      setConfirming(false)
      setConfirmOpen(false)
    }
  }

  function downloadTemplate() {
    downloadImportTemplate()
  }

  async function handleExport() {
    setExporting(true)
    try {
      const snapshot = await fetchExportSnapshot()
      downloadBackup(snapshot)
      message.success(
        `已导出备份：机柜 ${snapshot.cabinets.length}、资产 ${snapshot.assets.length}、部件 ${snapshot.components.length}`,
      )
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail ? `导出失败：${detail}` : '导出失败，请重试')
    } finally {
      setExporting(false)
    }
  }

  const previewColumns: TableColumnsType<ImportPreviewRow> = useMemo(
    () => [
      { title: '行号', dataIndex: 'row_no', width: 64, fixed: 'left' },
      {
        title: '状态',
        dataIndex: 'action',
        width: 92,
        fixed: 'left',
        render: (v: string) => (
          <Tag color={ACTION_META[v]?.color} icon={ACTION_META[v]?.icon}>
            {ACTION_META[v]?.label ?? v}
          </Tag>
        ),
      },
      { title: '物料类型', dataIndex: 'material_type', width: 100, render: fmt },
      { title: 'SN', dataIndex: 'sn', width: 140, render: fmt },
      { title: 'BMC IP', dataIndex: 'bmc_ip', width: 130, render: fmt },
      { title: '整机SN', dataIndex: 'machine_sn', width: 130, render: fmt },
      { title: '机柜', dataIndex: 'cabinet_name', width: 110, render: fmt },
      { title: 'U位', width: 80, render: (_, r) => uText(r) },
      { title: '资产SN', dataIndex: 'asset_sn', width: 130, render: fmt },
      { title: '挂账人', dataIndex: 'holder_name', width: 110, render: fmt },
      {
        title: '变动点',
        dataIndex: 'changes',
        width: 190,
        render: (_, r) =>
          r.changes.length === 0 ? (
            <Typography.Text type="secondary">—</Typography.Text>
          ) : (
            <div>
              {r.changes.map((c, i) => (
                <div key={i} style={{ fontSize: 12, lineHeight: 1.6 }}>
                  {FIELD_LABEL[c.field] ?? c.field}：{fmt(c.old)} → {fmt(c.new)}
                </div>
              ))}
            </div>
          ),
      },
      {
        title: '问题',
        dataIndex: 'issues',
        width: 260,
        render: (_, r) =>
          r.issues.length === 0 ? (
            <Typography.Text type="secondary">—</Typography.Text>
          ) : (
            <div>
              {r.issues.map((iss, i) => (
                <div
                  key={i}
                  style={{
                    fontSize: 12,
                    lineHeight: 1.6,
                    color: iss.severity === 'error' ? '#cf1322' : '#d48806',
                  }}
                >
                  {iss.severity === 'error' ? (
                    <ExclamationCircleFilled style={{ marginRight: 4 }} />
                  ) : (
                    <WarningFilled style={{ marginRight: 4 }} />
                  )}
                  {iss.message}
                </div>
              ))}
            </div>
          ),
      },
    ],
    [],
  )

  const resultColumns: TableColumnsType<ImportConfirmResponse['rows'][number]> = [
    { title: '行号', dataIndex: 'row_no', width: 80 },
    {
      title: '结果',
      dataIndex: 'result',
      width: 110,
      render: (v: string) => <Tag color={RESULT_META[v]?.color}>{RESULT_META[v]?.label ?? v}</Tag>,
    },
    { title: '物料类型', dataIndex: 'action', width: 100, render: fmt },
    {
      title: '说明',
      dataIndex: 'message',
      render: (v: string | null) =>
        v ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {v}
          </Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
  ]

  const batchColumns: TableColumnsType<ImportBatch> = [
    { title: '批次号', dataIndex: 'id', width: 80 },
    { title: '文件名', dataIndex: 'file_name', render: fmt },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (v: string) => (
        <Tag color={BATCH_STATUS_META[v]?.color}>{BATCH_STATUS_META[v]?.label ?? v}</Tag>
      ),
    },
    {
      title: '入库结果',
      width: 180,
      render: (_, b) => {
        const r = b.summary_json?.result
        if (!r) return <Typography.Text type="secondary">—</Typography.Text>
        return (
          <Space size={4} wrap>
            <Tag color="success">增 {r.created}</Tag>
            <Tag color="processing">改 {r.updated}</Tag>
            <Tag color="warning">跳 {r.skipped}</Tag>
          </Space>
        )
      },
    },
    { title: '时间', dataIndex: 'created_at', width: 180, render: (v: string) => fmtTime(v) },
    {
      title: '操作',
      width: 100,
      render: (_, b) => (
        <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => setDetailBatch(b)}>
          查看
        </Button>
      ),
    },
  ]

  const summary = preview?.summary
  const hasCommittable = summary ? summary.new + summary.update > 0 : false

  const detailRows: ImportRow[] = detailBatch?.summary_json?.rows ?? []
  const detailColumns: TableColumnsType<ImportRow> = [
    { title: 'BMC IP', dataIndex: 'bmc_ip', render: fmt },
    { title: '整机SN', dataIndex: 'machine_sn', render: fmt },
    { title: '物料类型', dataIndex: 'material_type', render: fmt },
    { title: 'SN', dataIndex: 'sn', render: fmt },
    { title: '物料编码', dataIndex: 'material_code', render: fmt },
    { title: '物料名称', dataIndex: 'material_name', render: fmt },
    { title: '备注', dataIndex: 'remark', render: fmt },
    { title: '挂账人', dataIndex: 'holder', render: fmt },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        title="物料导入"
        extra={
          <Space>
            {isAdmin && (
              <Button icon={<CloudDownloadOutlined />} loading={exporting} onClick={handleExport}>
                导出备份
              </Button>
            )}
            <Button icon={<DownloadOutlined />} onClick={downloadTemplate}>
              下载模板
            </Button>
          </Space>
        }
      >
        {phase !== 'done' && (
          <>
            <Upload.Dragger
              accept=".xlsx,.xls,.csv"
              maxCount={1}
              beforeUpload={beforeUpload}
              showUploadList={false}
              disabled={uploading}
            >
              {uploading ? (
                <Spin size="large" />
              ) : (
                <>
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">点击或拖拽物料表到此处上传</p>
                  <p className="ant-upload-hint">
                    支持 .xlsx / .xls / .csv；8 列：{IMPORT_HEADERS.join(' / ')}；挂账人格式「工号 姓名」
                  </p>
                </>
              )}
            </Upload.Dragger>
            {parseWarnings.length > 0 && (
              <Alert
                type="warning"
                showIcon
                style={{ marginTop: 12 }}
                message={parseWarnings.join('；')}
              />
            )}
          </>
        )}

        {preview && phase === 'preview' && summary && (
          <>
            <Space wrap style={{ marginTop: 20, marginBottom: 12 }}>
              <Tag>总 {summary.total} 行</Tag>
              <Tag color="success" icon={<PlusCircleOutlined />}>
                新增 {summary.new}
              </Tag>
              <Tag color="processing" icon={<SyncOutlined />}>
                更新 {summary.update}
              </Tag>
              {summary.warning > 0 && (
                <Tag color="warning" icon={<WarningFilled />}>
                  警告 {summary.warning}
                </Tag>
              )}
              {summary.error > 0 && (
                <Tag color="error" icon={<ExclamationCircleFilled />}>
                  错误 {summary.error}
                </Tag>
              )}
            </Space>
            <Table
              rowKey="row_no"
              columns={previewColumns}
              dataSource={preview.rows}
              size="small"
              scroll={{ x: 1560 }}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              rowClassName={(r) =>
                r.action === 'error'
                  ? 'import-row-error'
                  : r.issues.some((i) => i.severity === 'warning')
                    ? 'import-row-warning'
                    : ''
              }
            />
            <Space style={{ marginTop: 16 }}>
              <Button icon={<ReloadOutlined />} onClick={reset}>
                重新上传
              </Button>
              <Button type="primary" disabled={!hasCommittable} onClick={() => setConfirmOpen(true)}>
                确认入库
              </Button>
              {!hasCommittable && (
                <Typography.Text type="secondary">
                  没有可入库的行（全部为错误），请修正后重新上传
                </Typography.Text>
              )}
            </Space>
          </>
        )}

        {result && phase === 'done' && (
          <>
            <Alert
              type="success"
              showIcon
              icon={<CheckCircleFilled />}
              style={{ marginTop: 20 }}
              message={`入库完成：新增 ${result.summary.created}、更新 ${result.summary.updated}、跳过 ${result.summary.skipped}`}
              description="可在下方「导入历史」中回溯本次导入的原始数据与结果。"
            />
            <Table
              rowKey="row_no"
              columns={resultColumns}
              dataSource={result.rows}
              size="small"
              style={{ marginTop: 12 }}
              pagination={false}
            />
            <Button type="primary" style={{ marginTop: 16 }} icon={<ReloadOutlined />} onClick={reset}>
              再导一批
            </Button>
          </>
        )}
      </Card>

      <Card
        title="导入历史"
        extra={
          <Typography.Text type="secondary">
            <HistoryOutlined style={{ marginRight: 4 }} />
            每次上传都会留下批次记录，可追溯
          </Typography.Text>
        }
      >
        {batchesLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <Spin />
          </div>
        ) : batches.length === 0 ? (
          <Empty description="暂无导入记录" />
        ) : (
          <Table
            rowKey="id"
            columns={batchColumns}
            dataSource={batches}
            size="small"
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>

      <Modal
        title="确认入库"
        open={confirmOpen}
        onOk={doConfirm}
        onCancel={() => setConfirmOpen(false)}
        okText="确认入库"
        cancelText="取消"
        confirmLoading={confirming}
        okButtonProps={{ danger: true }}
      >
        {summary && (
          <>
            <Alert
              type="info"
              showIcon
              message={`将新增 ${summary.new} 个部件、更新 ${summary.update} 条记录`}
            />
            {summary.error > 0 && (
              <Alert
                type="warning"
                showIcon
                style={{ marginTop: 12 }}
                message={`${summary.error} 行有错误，将被跳过，不影响其它行入库`}
              />
            )}
            <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
              入库为不可逆操作，请在预览区核对「变动点」与「问题」后再确认。
            </Typography.Paragraph>
          </>
        )}
      </Modal>

      <Modal
        title={`批次 #${detailBatch?.id ?? ''} 原始数据`}
        open={detailBatch !== null}
        onCancel={() => setDetailBatch(null)}
        footer={null}
        width={1000}
      >
        {detailBatch && (
          <>
            <Space wrap style={{ marginBottom: 12 }}>
              <Tag color={BATCH_STATUS_META[detailBatch.status]?.color}>
                {BATCH_STATUS_META[detailBatch.status]?.label}
              </Tag>
              {detailBatch.summary_json?.result && (
                <>
                  <Tag color="success">增 {detailBatch.summary_json.result.created}</Tag>
                  <Tag color="processing">改 {detailBatch.summary_json.result.updated}</Tag>
                  <Tag color="warning">跳 {detailBatch.summary_json.result.skipped}</Tag>
                </>
              )}
            </Space>
            <Table
              rowKey={(_, i) => String(i)}
              columns={detailColumns}
              dataSource={detailRows}
              size="small"
              scroll={{ x: 800 }}
              pagination={false}
            />
          </>
        )}
      </Modal>
    </Space>
  )
}
