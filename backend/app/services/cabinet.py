"""机柜（Cabinet）业务逻辑。写操作仅总管理员，统一写 ChangeLog。"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.room import Room
from app.models.user import User
from app.permissions import require_admin
from app.schemas.cabinet import CabinetCreate, CabinetUpdate
from app.services import changelog


def _check_room(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None or room.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机房不存在")
    return room


def _check_name_unique(db: Session, room_id: int, name: str, exclude_id: int | None = None) -> None:
    query = db.query(Cabinet).filter(
        Cabinet.room_id == room_id,
        Cabinet.name == name,
        Cabinet.deleted_at.is_(None),
    )
    if exclude_id is not None:
        query = query.filter(Cabinet.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail=f"机柜 {name} 已存在于该机房")


def _validate_owner(db: Session, owner_id: int | None) -> None:
    if owner_id is None:
        return
    user = db.get(User, owner_id)
    if user is None or not user.active:
        raise HTTPException(status_code=422, detail="柜主用户不存在")
    if user.role != "cabinet_owner":
        raise HTTPException(status_code=422, detail="柜主必须是 cabinet_owner 角色")


def create_cabinet(db: Session, operator: User, data: CabinetCreate) -> Cabinet:
    require_admin(operator)
    _check_room(db, data.room_id)
    _check_name_unique(db, data.room_id, data.name)
    _validate_owner(db, data.owner_id)

    cab = Cabinet(**data.model_dump(), dept_id=settings.dept_id)
    db.add(cab)
    db.flush()
    changelog.log(
        db, operator=operator, target_type="cabinet", target_id=cab.id,
        cabinet_id=cab.id, action="create",
    )
    db.commit()
    db.refresh(cab)
    return cab


def update_cabinet(db: Session, operator: User, cabinet_id: int, data: CabinetUpdate) -> Cabinet:
    require_admin(operator)
    cab = db.get(Cabinet, cabinet_id)
    if cab is None or cab.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机柜不存在")

    changes = data.model_dump(exclude_unset=True)
    new_room_id = changes.get("room_id", cab.room_id)
    new_name = changes.get("name", cab.name)
    if "room_id" in changes:
        _check_room(db, new_room_id)
    if "room_id" in changes or "name" in changes:
        _check_name_unique(db, new_room_id, new_name, exclude_id=cab.id)
    if "owner_id" in changes:
        _validate_owner(db, changes["owner_id"])

    for field, value in changes.items():
        old = getattr(cab, field)
        if old == value:
            continue
        setattr(cab, field, value)
        changelog.log(
            db, operator=operator, target_type="cabinet", target_id=cab.id,
            cabinet_id=cab.id, action="update", field=field,
            old_value=old, new_value=value,
        )
    db.commit()
    db.refresh(cab)
    return cab


def delete_cabinet(db: Session, operator: User, cabinet_id: int) -> None:
    require_admin(operator)
    cab = db.get(Cabinet, cabinet_id)
    if cab is None or cab.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机柜不存在")

    active = (
        db.query(Asset)
        .filter(Asset.cabinet_id == cab.id, Asset.deleted_at.is_(None))
        .count()
    )
    if active > 0:
        raise HTTPException(status_code=409, detail=f"机柜内仍有 {active} 台设备，无法删除")

    cab.deleted_at = datetime.now(timezone.utc)
    changelog.log(
        db, operator=operator, target_type="cabinet", target_id=cab.id,
        cabinet_id=cab.id, action="delete",
    )
    db.commit()


def batch_assign_owner(
    db: Session, operator: User, cabinet_ids: list[int], owner_id: int | None
) -> int:
    require_admin(operator)
    _validate_owner(db, owner_id)

    updated = 0
    for cid in cabinet_ids:
        cab = db.get(Cabinet, cid)
        if cab is None or cab.deleted_at is not None:
            continue
        if cab.owner_id == owner_id:
            continue
        old = cab.owner_id
        cab.owner_id = owner_id
        changelog.log(
            db, operator=operator, target_type="cabinet", target_id=cab.id,
            cabinet_id=cab.id, action="update", field="owner_id",
            old_value=old, new_value=owner_id,
        )
        updated += 1
    db.commit()
    return updated


def get_cabinet(db: Session, cabinet_id: int) -> Cabinet:
    cab = db.get(Cabinet, cabinet_id)
    if cab is None or cab.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机柜不存在")
    return cab


def list_cabinets(
    db: Session,
    *,
    room_id: int | None = None,
    owner_id: int | None = None,
    skip: int = 0,
    limit: int = 200,
) -> tuple[list[Cabinet], int]:
    query = db.query(Cabinet).filter(Cabinet.deleted_at.is_(None))
    if room_id is not None:
        query = query.filter(Cabinet.room_id == room_id)
    if owner_id is not None:
        query = query.filter(Cabinet.owner_id == owner_id)
    total = query.count()
    items = (
        query.options(joinedload(Cabinet.owner), joinedload(Cabinet.room))
        .order_by(Cabinet.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, total
