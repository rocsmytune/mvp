// 全局展示常量：角色 / 资产类型 / 字段来源 / 变更动作 / 字典类别。
// 单一数据源，避免各页面重复定义导致术语、颜色不一致。

// 应用版本（首个 release）。页面页脚/登录页统一展示 v1.0.0。
export const APP_VERSION = '1.0.0'

export const ROLE_LABEL: Record<string, string> = {
  system_admin: '系统管理员',
  material_admin: '物料管理员',
  cabinet_owner: '柜主',
  member: '成员',
}

export const ROLE_COLOR: Record<string, string> = {
  system_admin: 'red',
  material_admin: 'geekblue',
  cabinet_owner: 'green',
  member: 'default',
}

// 资产类型：server 统一译作「服务器」（机柜图/详情/列表一致），
// 「整机」保留给导入列「整机SN」等语境，避免一词多义。
export const TYPE_LABEL: Record<string, string> = { server: '服务器', switch: '交换机' }
export const TYPE_COLOR: Record<string, string> = { server: 'blue', switch: 'orange' }

// 关键字段写入来源。
export const SOURCE_LABEL: Record<string, string> = { manual: '手工', import: '导入', bmc: 'BMC' }
export const SOURCE_COLOR: Record<string, string> = { manual: 'blue', import: 'green', bmc: 'purple' }

// 变更日志动作。
export const LOG_ACTION_LABEL: Record<string, string> = { create: '创建', update: '更新', delete: '删除' }
export const LOG_ACTION_COLOR: Record<string, string> = { create: 'green', update: 'blue', delete: 'red' }

// 字典类别。
export const DICT_KIND_LABEL: Record<string, string> = {
  asset_status: '资产状态',
  component_category: '部件物料类型',
}
