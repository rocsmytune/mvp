"""新增系统管理员角色，原总管理员(admin)改名为物料管理员(material_admin)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08

角色模型调整为四角色：
- system_admin 系统管理员：全权（含用户管理）
- material_admin 物料管理员：原 admin，物料+机柜+导入导出，不含用户管理
- cabinet_owner 柜主
- member 成员

存量 admin 用户自动改名为 material_admin。
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
    op.execute("UPDATE users SET role = 'material_admin' WHERE role = 'admin'")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('system_admin','material_admin','cabinet_owner','member'))"
    )


def downgrade() -> None:
    # 两个管理员角色合并回 admin；system_admin 用户回退后会变成 admin，属已知取舍。
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role")
    op.execute(
        "UPDATE users SET role = 'admin' WHERE role IN ('system_admin','material_admin')"
    )
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('admin','cabinet_owner','member'))"
    )
