-- 参考建表脚本（PostgreSQL 16）。实际以 Alembic 迁移为准，请让 AI 据此生成模型与迁移。
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE users (
  id            SERIAL PRIMARY KEY,
  employee_no   VARCHAR(32) UNIQUE NOT NULL,         -- 工号，用户主键语义
  name          VARCHAR(64) NOT NULL,
  role          VARCHAR(16) NOT NULL CHECK (role IN ('system_admin','material_admin','cabinet_owner','member')),
  auth_source   VARCHAR(16) NOT NULL DEFAULT 'local', -- local / sso
  password_hash VARCHAR(255),
  active        BOOLEAN NOT NULL DEFAULT TRUE,
  dept_id       INT NOT NULL DEFAULT 1,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rooms (
  id         SERIAL PRIMARY KEY,
  city       VARCHAR(32),
  code       VARCHAR(64) UNIQUE NOT NULL,             -- 如 SH-LQH-B13-B03-145R
  zone       VARCHAR(32),                             -- 如 绿区
  remark     TEXT,
  dept_id    INT NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ
);

CREATE TABLE cabinets (
  id         SERIAL PRIMARY KEY,
  room_id    INT NOT NULL REFERENCES rooms(id),
  name       VARCHAR(32) NOT NULL,                    -- 如 B01-16
  row_no     VARCHAR(16),                             -- B01
  col_no     INT,                                     -- 16
  total_u    INT NOT NULL DEFAULT 45,
  owner_id   INT REFERENCES users(id),                -- 柜主，可为空(待指派)
  dept_id    INT NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ,
  UNIQUE (room_id, name)
);
CREATE INDEX idx_cabinets_owner ON cabinets(owner_id);

CREATE TABLE assets (
  id           SERIAL PRIMARY KEY,
  type         VARCHAR(16) NOT NULL CHECK (type IN ('server','switch')),
  cabinet_id   INT REFERENCES cabinets(id),           -- 待整理池时为空
  u_start      INT,
  u_end        INT,
  sn           VARCHAR(64),
  asset_tag    VARCHAR(64),                           -- 资产编号
  model        VARCHAR(128),
  cpu_model    VARCHAR(128),
  ip_inband    VARCHAR(45),                           -- 带内IP（交换机=管理IP）
  bmc_ip       VARCHAR(45),                           -- 带外IP
  status       VARCHAR(16) NOT NULL DEFAULT 'in_use', -- 字典管理
  in_pool      BOOLEAN NOT NULL DEFAULT FALSE,        -- 待整理池
  location_raw TEXT,                                  -- 导入的位置原文
  pool_reason  VARCHAR(64),                           -- parse_error / u_overlap / u_out_of_range ...
  field_source JSONB NOT NULL DEFAULT '{}',           -- {"cpu_model":"import","sn":"manual"}
  remark       TEXT,
  holder_id    INT REFERENCES users(id),              -- 挂账人（仅交换机 type='switch'；服务器不挂账）
  holder_name  VARCHAR(64),                           -- 挂账人姓名快照（工号匹配不到时保留原文）
  dept_id      INT NOT NULL DEFAULT 1,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at   TIMESTAMPTZ,
  CHECK (u_start IS NULL OR (u_start >= 1 AND u_end >= u_start AND u_end <= 45)),
  CHECK ((cabinet_id IS NULL) = (u_start IS NULL)),
  -- 同一机柜内U位不得重叠
  EXCLUDE USING gist (
    cabinet_id WITH =,
    int4range(u_start, u_end, '[]') WITH &&
  ) WHERE (deleted_at IS NULL AND cabinet_id IS NOT NULL)
);
CREATE INDEX idx_assets_sn ON assets(sn);
CREATE INDEX idx_assets_bmc_ip ON assets(bmc_ip);
CREATE INDEX idx_assets_ip_inband ON assets(ip_inband);
CREATE INDEX idx_assets_cabinet ON assets(cabinet_id);
CREATE INDEX idx_assets_pool ON assets(in_pool) WHERE deleted_at IS NULL;

-- 2026-10-01：为「手工物料表格导入」补齐字段。导入表列为
-- BMC IP / 整机SN / 物料类型 / SN / 物料编码 / 物料名称 / 备注 / 挂账人，
-- 其中 物料编码→material_code、物料名称→name、挂账人→holder_id+holder_name。
-- 挂账人落在：部件（components）与交换机（assets，type='switch'）；
-- 服务器整机（type='server'）不挂账，有价值的部件才单独建账。
CREATE TABLE components (
  id            SERIAL PRIMARY KEY,
  asset_id      INT NOT NULL REFERENCES assets(id),
  category      VARCHAR(32) NOT NULL,   -- cpu/memory/disk/nic/optical/board/cable/fan...
  sn            VARCHAR(64),            -- 物料自身 SN（数量管理类可为空）
  model         VARCHAR(128),
  name          VARCHAR(255),           -- 物料名称（text，后期正则解析）
  material_code VARCHAR(64),            -- 物料编码（同类型同型号料号，如 03045A）
  qty           INT NOT NULL DEFAULT 1,
  sn_source     VARCHAR(16) NOT NULL DEFAULT 'manual', -- import / manual / bmc
  remark        TEXT,
  holder_id     INT REFERENCES users(id), -- 挂账人（关联 users）
  holder_name   VARCHAR(64),            -- 挂账人姓名快照（工号匹配不到时保留原文）
  dept_id       INT NOT NULL DEFAULT 1,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_components_sn ON components(sn);   -- 不加唯一约束，重复只提示
CREATE INDEX idx_components_asset ON components(asset_id);

CREATE TABLE change_logs (
  id          BIGSERIAL PRIMARY KEY,
  target_type VARCHAR(16) NOT NULL,   -- asset / component / cabinet / room / user
  target_id   INT NOT NULL,
  cabinet_id  INT,                    -- 冗余，便于柜主按机柜查看日志
  action      VARCHAR(16) NOT NULL,   -- create / update / delete / restore
  field       VARCHAR(64),
  old_value   TEXT,
  new_value   TEXT,
  operator_id INT REFERENCES users(id),
  source      VARCHAR(16) NOT NULL DEFAULT 'manual', -- manual / import / bmc
  batch_id    INT,                    -- 关联导入批次
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_logs_target ON change_logs(target_type, target_id);
CREATE INDEX idx_logs_cabinet ON change_logs(cabinet_id, created_at DESC);

CREATE TABLE import_batches (
  id           SERIAL PRIMARY KEY,
  file_name    VARCHAR(255),
  operator_id  INT REFERENCES users(id),
  status       VARCHAR(16) NOT NULL DEFAULT 'previewed', -- previewed / committed / cancelled
  summary_json JSONB,                 -- 新增/更新/冲突/进池/错误计数与明细
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE dictionaries (
  id       SERIAL PRIMARY KEY,
  kind     VARCHAR(32) NOT NULL,      -- asset_status / component_category
  code     VARCHAR(32) NOT NULL,
  label    VARCHAR(64) NOT NULL,
  sort_no  INT NOT NULL DEFAULT 0,
  UNIQUE (kind, code)
);
