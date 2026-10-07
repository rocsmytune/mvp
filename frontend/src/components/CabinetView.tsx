import { Tooltip } from 'antd'
import type { Asset } from '../api/types'

// 机柜 U 位图：原生 SVG 绘制机柜框架（U 号标签 + 导轨 + 槽位线），
// 设备块用 HTML 绝对定位叠加在框架上，便于 Tooltip 与点击交互。
// 前视视角：U45 在顶部、U1 在底部（与「U1 在底部」数据约定一致）。

const SLOT_H = 30 // 每 U 高度 px
const LABEL_W = 30 // 左侧 U 号标签栏宽
const BODY_W = 216 // 机柜主体宽
const GAP = 6 // 标签栏与主体间距

const TYPE_META: Record<string, { label: string; bg: string; border: string; text: string }> = {
  server: { label: '服务器', bg: '#e6f4ff', border: '#91caff', text: '#0958d9' },
  switch: { label: '交换机', bg: '#fff7e6', border: '#ffd591', text: '#d46b08' },
}

function uText(a: Asset): string {
  if (a.u_start == null || a.u_end == null) return '—'
  return a.u_start === a.u_end ? `${a.u_start}U` : `${a.u_start}-${a.u_end}U`
}

interface CabinetViewProps {
  assets: Asset[]
  totalU?: number
  onSelect?: (asset: Asset) => void
  onPlace?: (u: number) => void
}

export default function CabinetView({ assets, totalU = 45, onSelect, onPlace }: CabinetViewProps) {
  const width = LABEL_W + GAP + BODY_W
  const height = totalU * SLOT_H + 2
  const bodyX = LABEL_W + GAP

  // 已占用的 U 位集合（空槽据此渲染「在此上架」点击层）。
  const occupied = new Set<number>()
  assets.forEach((a) => {
    if (a.u_start != null && a.u_end != null) {
      for (let u = a.u_start; u <= a.u_end; u++) occupied.add(u)
    }
  })

  return (
    <div style={{ position: 'relative', width, height, flexShrink: 0 }}>
      <svg
        width={width}
        height={height}
        style={{ position: 'absolute', top: 0, left: 0 }}
      >
        {/* 机柜主体 */}
        <rect
          x={bodyX}
          y={1}
          width={BODY_W}
          height={totalU * SLOT_H}
          fill="#fafafa"
          stroke="#d9d9d9"
          strokeWidth={1}
        />
        {/* 左右导轨 */}
        <rect x={bodyX} y={1} width={8} height={totalU * SLOT_H} fill="#f0f0f0" />
        <rect x={bodyX + BODY_W - 8} y={1} width={8} height={totalU * SLOT_H} fill="#f0f0f0" />
        {/* 槽位分隔线 */}
        {Array.from({ length: totalU + 1 }, (_, i) => (
          <line
            key={i}
            x1={bodyX + 8}
            x2={bodyX + BODY_W - 8}
            y1={i * SLOT_H + 1}
            y2={i * SLOT_H + 1}
            stroke="#f0f0f0"
            strokeWidth={1}
          />
        ))}
        {/* U 号标签：顶部 U45 递减到底部 U1 */}
        {Array.from({ length: totalU }, (_, i) => {
          const u = totalU - i
          return (
            <text
              key={u}
              x={LABEL_W - 4}
              y={(i + 0.5) * SLOT_H + 4}
              textAnchor="end"
              fontSize={11}
              fill="#8c8c8c"
            >
              {u}
            </text>
          )
        })}
      </svg>

      {/* 设备块（HTML 叠加，便于交互） */}
      {assets.map((a) => {
        if (a.u_start == null || a.u_end == null) return null
        const top = (totalU - a.u_end) * SLOT_H + 1
        const blockH = (a.u_end - a.u_start + 1) * SLOT_H - 2
        const meta = TYPE_META[a.type] ?? TYPE_META.server
        const primary = a.model || a.sn || a.asset_tag || meta.label
        const secondary = a.model ? a.sn || null : null
        return (
          <Tooltip
            key={a.id}
            title={
              <div>
                <div>
                  {meta.label} · {a.model ?? '—'}
                </div>
                <div>SN：{a.sn ?? '—'}</div>
                <div>BMC IP：{a.bmc_ip ?? '—'}</div>
                <div>U位：{uText(a)}</div>
              </div>
            }
          >
            <div
              onClick={() => onSelect?.(a)}
              style={{
                position: 'absolute',
                left: bodyX + 12,
                top,
                width: BODY_W - 24,
                height: blockH,
                background: meta.bg,
                border: `1px solid ${meta.border}`,
                borderRadius: 3,
                padding: '2px 8px',
                cursor: onSelect ? 'pointer' : 'default',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
              }}
            >
              <div
                style={{
                  color: meta.text,
                  fontSize: 12,
                  fontWeight: 600,
                  lineHeight: 1.3,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {primary}
              </div>
              {secondary && (
                <div
                  style={{
                    color: '#8c8c8c',
                    fontSize: 11,
                    lineHeight: 1.3,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {secondary}
                </div>
              )}
            </div>
          </Tooltip>
        )
      })}

      {/* 空槽点击层：仅在有上架回调时渲染（即可管理该柜） */}
      {onPlace &&
        Array.from({ length: totalU }, (_, i) => {
          const u = totalU - i
          if (occupied.has(u)) return null
          const top = (totalU - u) * SLOT_H + 1
          return (
            <div
              key={`slot-${u}`}
              className="u-slot-empty"
              title={`U${u} 在此上架`}
              onClick={() => onPlace(u)}
              style={{
                left: bodyX + 12,
                top,
                width: BODY_W - 24,
                height: SLOT_H - 2,
              }}
            >
              <span className="u-slot-empty-hint">在此上架</span>
            </div>
          )
        })}
    </div>
  )
}
