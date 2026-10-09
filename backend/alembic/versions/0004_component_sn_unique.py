"""部件 SN 在同类型下唯一

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-09

E1：相同物料类型（category）下 SN 必须唯一。用部分唯一索引约束未删除且 SN 非空的部件，
数据库层兜底；服务层同步校验返回友好错误，手动导入按 category+sn 去重只覆盖不新增。
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_components_category_sn",
        "components",
        ["category", "sn"],
        unique=True,
        postgresql_where="deleted_at IS NULL AND sn IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_components_category_sn", table_name="components")
