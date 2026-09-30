"""集中导入所有模型，确保 Base.metadata 注册完整（Alembic 依赖它）。"""

from app.models.asset import Asset
from app.models.base import Base
from app.models.cabinet import Cabinet
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.dictionary import Dictionary
from app.models.import_batch import ImportBatch
from app.models.room import Room
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Room",
    "Cabinet",
    "Asset",
    "Component",
    "ChangeLog",
    "ImportBatch",
    "Dictionary",
]
