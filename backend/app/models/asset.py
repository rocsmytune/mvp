from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Asset(Base):
    """整机设备：服务器 / 交换机。cabinet_id 为空表示进入待整理池。"""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("type IN ('server','switch')", name="ck_assets_type"),
        CheckConstraint(
            "(u_start IS NULL) OR (u_start >= 1 AND u_end >= u_start AND u_end <= 45)",
            name="ck_assets_u_range",
        ),
        CheckConstraint("(cabinet_id IS NULL) = (u_start IS NULL)", name="ck_assets_pool_u"),
        Index("idx_assets_sn", "sn"),
        Index("idx_assets_bmc_ip", "bmc_ip"),
        Index("idx_assets_ip_inband", "ip_inband"),
        Index("idx_assets_cabinet", "cabinet_id"),
        Index("idx_assets_pool", "in_pool", postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    cabinet_id: Mapped[int | None] = mapped_column(ForeignKey("cabinets.id"), nullable=True)
    u_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    u_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    asset_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cpu_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_inband: Mapped[str | None] = mapped_column(String(45), nullable=True)
    bmc_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="'in_use'")
    in_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    location_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    pool_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 关键字段来源：{"cpu_model":"import","sn":"manual","ip_inband":"bmc",...}
    field_source: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 挂账人：仅交换机（type='switch'）使用；服务器整机不挂账。
    holder_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dept_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
