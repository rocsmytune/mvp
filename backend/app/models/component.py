from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Component(Base):
    """部件：单件管理（有SN）或数量管理（无SN，记型号与数量）。"""

    __tablename__ = "components"
    __table_args__ = (
        Index("idx_components_sn", "sn"),
        Index("idx_components_asset", "asset_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    sn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # 物料导入字段：物料名称（text，后期正则解析）与物料编码（同类型同型号料号）。
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    material_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    sn_source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="'manual'")
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 挂账人：holder_id 关联 users；holder_name 存姓名快照（工号匹配不到时保留原文）。
    holder_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    holder_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dept_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
