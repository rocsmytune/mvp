from datetime import datetime

from pydantic import BaseModel


class ChangeLogOut(BaseModel):
    """变更日志条目（带操作人姓名快照，供设备详情展示）。"""

    id: int
    target_type: str
    target_id: int
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    source: str
    operator_id: int | None
    operator_name: str | None
    batch_id: int | None
    created_at: datetime
