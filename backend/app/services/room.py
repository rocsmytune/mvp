"""机房（Room）业务逻辑。写操作仅总管理员，统一写 ChangeLog。"""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.cabinet import Cabinet
from app.models.room import Room
from app.models.user import User
from app.permissions import require_admin
from app.schemas.room import RoomCreate, RoomUpdate
from app.services import changelog


def _check_code_unique(db: Session, code: str, exclude_id: int | None = None) -> None:
    query = db.query(Room).filter(Room.code == code, Room.deleted_at.is_(None))
    if exclude_id is not None:
        query = query.filter(Room.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail=f"机房编码 {code} 已存在")


def create_room(db: Session, operator: User, data: RoomCreate) -> Room:
    require_admin(operator)
    _check_code_unique(db, data.code)

    room = Room(**data.model_dump(), dept_id=settings.dept_id)
    db.add(room)
    db.flush()
    changelog.log(
        db, operator=operator, target_type="room", target_id=room.id,
        cabinet_id=None, action="create",
    )
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, operator: User, room_id: int, data: RoomUpdate) -> Room:
    require_admin(operator)
    room = db.get(Room, room_id)
    if room is None or room.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机房不存在")

    changes = data.model_dump(exclude_unset=True)
    if "code" in changes and changes["code"] != room.code:
        _check_code_unique(db, changes["code"], exclude_id=room.id)
    for field, value in changes.items():
        old = getattr(room, field)
        if old == value:
            continue
        setattr(room, field, value)
        changelog.log(
            db, operator=operator, target_type="room", target_id=room.id,
            cabinet_id=None, action="update", field=field,
            old_value=old, new_value=value,
        )
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, operator: User, room_id: int) -> None:
    require_admin(operator)
    room = db.get(Room, room_id)
    if room is None or room.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机房不存在")

    active = (
        db.query(Cabinet)
        .filter(Cabinet.room_id == room.id, Cabinet.deleted_at.is_(None))
        .count()
    )
    if active > 0:
        raise HTTPException(status_code=409, detail=f"机房内仍有 {active} 个机柜，无法删除")

    room.deleted_at = datetime.now(timezone.utc)
    changelog.log(
        db, operator=operator, target_type="room", target_id=room.id,
        cabinet_id=None, action="delete",
    )
    db.commit()


def get_room(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None or room.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机房不存在")
    return room


def list_rooms(db: Session, *, q: str | None = None, skip: int = 0, limit: int = 100) -> tuple[list[Room], int]:
    query = db.query(Room).filter(Room.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Room.code.ilike(like), Room.city.ilike(like), Room.zone.ilike(like))
        )
    total = query.count()
    items = query.order_by(Room.id).offset(skip).limit(limit).all()
    return items, total
