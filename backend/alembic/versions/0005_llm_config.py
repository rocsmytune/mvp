"""AI 助手 LLM 配置与用量表

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-10

- app_settings：全局默认 LLM 配置（单行，id 固定 1）
- user_llm_config：每用户个人 LLM 配置（api_key 加密存储）
- llm_usage：每用户每日 token 用量（配额累计）
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("llm_base_url", sa.String(length=500), nullable=True),
        sa.Column("llm_api_key_enc", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column(
            "daily_token_quota",
            sa.Integer(),
            nullable=False,
            server_default="50000",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "user_llm_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("llm_base_url", sa.String(length=500), nullable=True),
        sa.Column("llm_api_key_enc", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=128), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", name="uq_user_llm_config_user"),
    )

    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_llm_usage_user_date"),
    )
    op.create_index("ix_llm_usage_user_id", "llm_usage", ["user_id"])


def downgrade() -> None:
    op.drop_table("llm_usage")
    op.drop_table("user_llm_config")
    op.drop_table("app_settings")
