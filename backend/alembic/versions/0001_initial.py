"""初始表结构

Revision ID: 0001
Revises:
Create Date: 2026-09-30

与 docs/schema.sql 对齐。U 位不重叠约束用 btree_gist 的排除约束实现。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_no", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("auth_source", sa.String(length=16), nullable=False, server_default="'local'"),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("dept_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('admin','cabinet_owner','member')", name="ck_users_role"),
        sa.UniqueConstraint("employee_no"),
    )

    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("city", sa.String(length=32), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("zone", sa.String(length=32), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("dept_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "cabinets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("row_no", sa.String(length=16), nullable=True),
        sa.Column("col_no", sa.Integer(), nullable=True),
        sa.Column("total_u", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dept_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("room_id", "name"),
    )
    op.create_index("idx_cabinets_owner", "cabinets", ["owner_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("cabinet_id", sa.Integer(), sa.ForeignKey("cabinets.id"), nullable=True),
        sa.Column("u_start", sa.Integer(), nullable=True),
        sa.Column("u_end", sa.Integer(), nullable=True),
        sa.Column("sn", sa.String(length=64), nullable=True),
        sa.Column("asset_tag", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("cpu_model", sa.String(length=128), nullable=True),
        sa.Column("ip_inband", sa.String(length=45), nullable=True),
        sa.Column("bmc_ip", sa.String(length=45), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="'in_use'"),
        sa.Column("in_pool", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("location_raw", sa.Text(), nullable=True),
        sa.Column("pool_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "field_source", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("dept_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('server','switch')", name="ck_assets_type"),
        sa.CheckConstraint(
            "(u_start IS NULL) OR (u_start >= 1 AND u_end >= u_start AND u_end <= 45)",
            name="ck_assets_u_range",
        ),
        sa.CheckConstraint("(cabinet_id IS NULL) = (u_start IS NULL)", name="ck_assets_pool_u"),
    )
    op.create_index("idx_assets_sn", "assets", ["sn"])
    op.create_index("idx_assets_bmc_ip", "assets", ["bmc_ip"])
    op.create_index("idx_assets_ip_inband", "assets", ["ip_inband"])
    op.create_index("idx_assets_cabinet", "assets", ["cabinet_id"])
    op.create_index(
        "idx_assets_pool", "assets", ["in_pool"], postgresql_where=sa.text("deleted_at IS NULL")
    )

    op.create_table(
        "components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("sn", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sn_source", sa.String(length=16), nullable=False, server_default="'manual'"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("dept_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_components_sn", "components", ["sn"])
    op.create_index("idx_components_asset", "components", ["asset_id"])

    op.create_table(
        "change_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("cabinet_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("field", sa.String(length=64), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="'manual'"),
        sa.Column("batch_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_logs_target", "change_logs", ["target_type", "target_id"])
    op.create_index("idx_logs_cabinet", "change_logs", ["cabinet_id", "created_at"])

    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="'previewed'"),
        sa.Column("summary_json", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "dictionaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("sort_no", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("kind", "code"),
    )

    # 同一机柜内未删除设备的 U 位区间不得重叠（数据库层兜底，服务层另有友好校验）。
    op.execute(
        """
        ALTER TABLE assets ADD CONSTRAINT assets_u_no_overlap
        EXCLUDE USING gist (
            cabinet_id WITH =,
            int4range(u_start, u_end, '[]') WITH &&
        ) WHERE (deleted_at IS NULL AND cabinet_id IS NOT NULL)
        """
    )


def downgrade() -> None:
    op.drop_table("dictionaries")
    op.drop_table("import_batches")
    op.drop_table("change_logs")
    op.drop_table("components")
    op.drop_table("assets")
    op.drop_table("cabinets")
    op.drop_table("rooms")
    op.drop_table("users")
    # btree_gist 扩展本身保留（可能被其它对象使用），不在此删除。
