from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Cabinet(Base):
    """机柜：45U，U1 在底部；owner 为空表示待指派柜主。"""

    __tablename__ = "cabinets"
    __table_args__ = (
        UniqueConstraint("room_id", "name"),
        Index("idx_cabinets_owner", "owner_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    row_no: Mapped[str | None] = mapped_column(String(16), nullable=True)
    col_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_u: Mapped[int] = mapped_column(Integer, nullable=False, server_default="45")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    dept_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User | None"] = relationship()
    room: Mapped["Room"] = relationship()

    @property
    def owner_name(self) -> str | None:
        return self.owner.name if self.owner else None

    @property
    def room_code(self) -> str | None:
        return self.room.code if self.room else None
