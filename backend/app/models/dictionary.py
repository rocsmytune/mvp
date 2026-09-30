from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Dictionary(Base):
    """字典：asset_status / component_category 等枚举。"""

    __tablename__ = "dictionaries"
    __table_args__ = (UniqueConstraint("kind", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
