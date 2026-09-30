"""为手工物料表格导入补齐字段

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01

导入表列为：BMC IP / 整机SN / 物料类型 / SN / 物料编码 / 物料名称 / 备注 / 挂账人。
- components 新增 name(物料名称)、material_code(物料编码)、holder_id/holder_name(挂账人)
- assets 新增 holder_id/holder_name：仅交换机（type='switch'）挂账；服务器整机不挂账。
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("components", sa.Column("name", sa.String(length=255), nullable=True))
    op.add_column(
        "components", sa.Column("material_code", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "components",
        sa.Column("holder_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "components", sa.Column("holder_name", sa.String(length=64), nullable=True)
    )

    op.add_column(
        "assets",
        sa.Column("holder_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("assets", sa.Column("holder_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "holder_name")
    op.drop_column("assets", "holder_id")
    op.drop_column("components", "holder_name")
    op.drop_column("components", "holder_id")
    op.drop_column("components", "material_code")
    op.drop_column("components", "name")
