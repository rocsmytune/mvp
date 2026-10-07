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


def list_for_asset(db: Session, asset_id: int) -> list[dict]:
    """某资产的变更日志（含操作人姓名），按时间倒序。只读，不做角色过滤（与其它读接口一致）。"""
    rows = (
        db.query(ChangeLog, User.name)
        .outerjoin(User, User.id == ChangeLog.operator_id)
        .filter(ChangeLog.target_type == "asset", ChangeLog.target_id == asset_id)
        .order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        .all()
    )
    return [
        {
            "id": log.id,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "action": log.action,
            "field": log.field,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "source": log.source,
            "operator_id": log.operator_id,
            "operator_name": operator_name,
            "batch_id": log.batch_id,
            "created_at": log.created_at,
        }
        for log, operator_name in rows
    ]
