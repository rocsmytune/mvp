"""ChangeLog 统一写入。所有写操作由服务层调用本模块，自动记录变更。"""

from sqlalchemy.orm import Session

from app.models.change_log import ChangeLog
from app.models.user import User


def log(
    db: Session,
    *,
    operator: User | None,
    target_type: str,
    target_id: int,
    cabinet_id: int | None,
    action: str,
    field: str | None = None,
    old_value: object = None,
    new_value: object = None,
    source: str = "manual",
    batch_id: int | None = None,
) -> None:
    db.add(
        ChangeLog(
            target_type=target_type,
            target_id=target_id,
            cabinet_id=cabinet_id,
            action=action,
            field=field,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            operator_id=operator.id if operator is not None else None,
            source=source,
            batch_id=batch_id,
        )
    )
