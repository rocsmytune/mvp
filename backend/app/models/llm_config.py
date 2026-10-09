"""AI 助手（chatbot）相关配置与用量模型。

三张表：
- app_settings：全局默认 LLM 配置（单行，id 固定 1），仅 system_admin 可改。
- user_llm_config：每用户个人 LLM 配置（覆盖全局默认），key 加密存储。
- llm_usage：每用户每日 token 用量，用于默认 API 的配额累计。
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    llm_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # api_key 经 core.crypto.encrypt_secret 加密存储，绝不落明文。
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 走默认 API 时每用户每日 token 配额。
    daily_token_quota: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50000"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class UserLlmConfig(Base):
    __tablename__ = "user_llm_config"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_llm_config_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    llm_base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    llm_api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    __table_args__ = (UniqueConstraint("user_id", "usage_date", name="uq_llm_usage_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
