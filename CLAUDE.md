# CLAUDE.md（同样可命名为 AGENTS.md 供 Codex 使用）

## 项目
机柜物料管理平台，单部门内网使用，规模500–1000台设备、500用户。
阶段1范围见 `docs/PRD_phase1.md`。**不要实现PRD范围外的功能。**

## 技术栈
- 后端：Python 3.11 + FastAPI + SQLAlchemy 2.x + Alembic + pytest
- 数据库：PostgreSQL 16（需要 btree_gist 扩展）
- 前端：React + TypeScript + Vite + Ant Design；机柜图使用原生SVG
- 部署：docker compose（backend / frontend / db）
- 不引入：Celery、Redis、微服务、GraphQL、ORM之外的第二套数据访问方式

## 目录结构
```
repo/
├─ CLAUDE.md
├─ docs/                  PRD、schema.sql、字段映射
├─ docker-compose.yml
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ core/            配置、安全、依赖注入
│  │  ├─ auth/            认证（可替换：local.py，预留 sso.py）
│  │  ├─ models/          SQLAlchemy模型
│  │  ├─ schemas/         Pydantic模型
│  │  ├─ services/        业务逻辑（所有写操作在此，统一写ChangeLog）
│  │  ├─ api/             路由，仅做参数校验+调用services
│  │  ├─ importer/        Excel解析、位置解析、去重、预览
│  │  └─ permissions.py   权限判断（唯一入口）
│  ├─ alembic/
│  └─ tests/
└─ frontend/
   └─ src/ pages/ components/(CabinetView.tsx 等) api/ store/
```

## 硬性规则
1. **权限**：每个写接口和敏感读接口必须通过 `permissions.py` 校验，前端隐藏按钮不算权限。柜主只能操作 owner 为自己的机柜内的资产。
2. **统一写入**：所有对 Asset / Component / Cabinet 的增改删必须走 `services/`，由服务层自动写 ChangeLog。禁止在路由里直接改库。
3. **软删除**：使用 `deleted_at`，查询默认过滤已删除。
4. **迁移**：表结构只能通过 Alembic 迁移修改，禁止手改库或 `create_all`。
5. **U位规则**：机柜45U，U1在底部；同一机柜内未删除设备的U区间不得重叠（数据库有排除约束，服务层也要校验并返回友好错误）。
6. **字段来源**：关键字段（cpu_model、sn、ip等）写入时记录 source（import/manual/bmc）。`manual` 的值不被 `import`/`bmc` 静默覆盖。
7. **认证可替换**：用户主键是工号 `employee_no`；认证逻辑只放在 `auth/`，业务代码只依赖 `get_current_user`。
8. **导入不失败原则**：位置解析失败或冲突的行进入待整理池（in_pool=true，保存 location_raw 与 pool_reason），不得因单行错误中断整批导入。
9. **SN重复**：部件SN重复只提示冲突，不硬性拒绝。
10. **保留 dept_id**：所有主表带 dept_id，当前固定为同一个值，不做多租户逻辑。

## 位置解析规则（importer/location.py）
- 所属实验室：`城市/机房编码/区域`，按 `/` 拆三段。
- 机架号：正则 `^([A-Za-z]+\d+)-(\d+)$`，机柜名=原文，row/col 另存。
- U数：`^(\d+)(?:\s*[-~–]\s*(\d+))?$`，u_start=min，u_end=max，u_size=end-start+1；范围 1–45。
- 机柜不存在则自动创建（owner为空）。
- 去重键：bmc_ip > ip_inband。

## 测试要求（必须写）
- 权限：三种角色 × 主要写接口的允许/拒绝用例
- 位置解析：合法/非法/边界（U越界、单值、乱序如`23-22`、空值）
- U位重叠校验
- 导入：重复导入幂等、manual字段不被覆盖、冲突进池
- ChangeLog：每类写操作均产生日志

## 数据与合规
- 仓库、提示词、测试中**只使用脱敏或构造数据**，禁止出现真实IP、SN、人员信息。
- 种子数据用 `backend/tests/fixtures/` 里的构造数据。

## 工作方式
- 一次只做一个小功能（一个接口+对应测试，或一个页面），完成并测试通过后再继续。
- 改动数据模型前先更新 `docs/schema.sql` 并说明理由。
- 不确定时提问，不要自行扩展需求。
