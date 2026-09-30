# 机柜物料管理平台

阶段1：物料管理与查询、机柜可视化、多角色鉴权。范围见 `docs/PRD_phase1.md`。

## 快速开始（Docker）

```bash
docker compose up --build
```

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/health
- 数据库：localhost:5432（库名/用户/密码均为 `mvp`，开发用）

后端启动时自动执行 `alembic upgrade head` 建表。

## 本地开发（不打包 Docker）

后端：

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head          # 建表（需先有 PostgreSQL 在 localhost:5432）
.venv/bin/uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 测试

```bash
cd backend
.venv/bin/pytest
```

## 数据库迁移

表结构只通过 Alembic 迁移修改（见 `backend/alembic/`），禁止手改库或 `create_all`。

```bash
cd backend
alembic revision --autogenerate -m "描述"   # 生成迁移
alembic upgrade head                        # 应用
```
