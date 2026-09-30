"""机房总览聚合数据：已上架/待整理数量、机房列表、机柜及其设备统计。"""

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.room import Room
from app.schemas.room import RoomOut


def get_overview(db: Session) -> dict:
    rooms = db.query(Room).filter(Room.deleted_at.is_(None)).order_by(Room.id).all()
    cabinets = (
        db.query(Cabinet)
        .options(joinedload(Cabinet.owner), joinedload(Cabinet.room))
        .filter(Cabinet.deleted_at.is_(None))
        .order_by(Cabinet.id)
        .all()
    )
    rows = (
        db.query(
            Asset.cabinet_id,
            func.count(Asset.id),
            func.coalesce(func.sum(Asset.u_end - Asset.u_start + 1), 0),
        )
        .filter(Asset.deleted_at.is_(None), Asset.cabinet_id.isnot(None))
        .group_by(Asset.cabinet_id)
        .all()
    )
    stats = {cab_id: (cnt, used) for cab_id, cnt, used in rows}

    cabinet_items = []
    for c in cabinets:
        cnt, used = stats.get(c.id, (0, 0))
        cabinet_items.append(
            {
                "id": c.id,
                "room_id": c.room_id,
                "room_code": c.room.code if c.room else None,
                "name": c.name,
                "owner_id": c.owner_id,
                "owner_name": c.owner.name if c.owner else None,
                "total_u": c.total_u,
                "device_count": cnt,
                "used_u": used,
            }
        )

    placed_count = (
        db.query(Asset)
        .filter(Asset.deleted_at.is_(None), Asset.in_pool.is_(False))
        .count()
    )
    pool_count = (
        db.query(Asset)
        .filter(Asset.deleted_at.is_(None), Asset.in_pool.is_(True))
        .count()
    )

    return {
        "placed_count": placed_count,
        "pool_count": pool_count,
        "rooms": [RoomOut.model_validate(r) for r in rooms],
        "cabinets": cabinet_items,
    }
