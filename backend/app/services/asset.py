"""设备（Asset）业务逻辑。所有写操作在此，统一写 ChangeLog 并做权限/U 位校验。"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.room import Room
from app.models.user import User
from app.permissions import ensure_can_manage_cabinet
from app.schemas.asset import AssetCreate, AssetUpdate
from app.services import changelog

# 关键字段：写入时记录来源，manual 值不被 import/bmc 静默覆盖（规则6）
TRACKED_FIELDS = ("cpu_model", "sn", "ip_inband", "bmc_ip")


def _get_cabinet(db: Session, cabinet_id: int | None) -> Cabinet | None:
    if cabinet_id is None:
        return None
    cabinet = db.get(Cabinet, cabinet_id)
    if cabinet is None or cabinet.deleted_at is not None:
        raise HTTPException(status_code=404, detail="机柜不存在")
    return cabinet


def _validate_u(
    db: Session,
    cabinet_id: int | None,
    u_start: int | None,
    u_end: int | None,
    exclude_id: int | None = None,
) -> None:
    """U 位校验：池内不设 U；机柜内必须有合法 U 且不得与未删除设备重叠。"""
    if cabinet_id is None:
        if u_start is not None or u_end is not None:
            raise HTTPException(status_code=422, detail="待整理池设备不应指定 U 位")
        return
    if u_start is None or u_end is None:
        raise HTTPException(status_code=422, detail="机柜内设备必须指定 U 位")
    if not (1 <= u_start <= u_end <= 45):
        raise HTTPException(
            status_code=422, detail="U 位非法：需满足 1 ≤ u_start ≤ u_end ≤ 45"
        )
    query = db.query(Asset).filter(
        Asset.cabinet_id == cabinet_id, Asset.deleted_at.is_(None)
    )
    if exclude_id is not None:
        query = query.filter(Asset.id != exclude_id)
    for other in query.all():
        if not (u_end < other.u_start or u_start > other.u_end):
            label = other.sn or f"#{other.id}"
            raise HTTPException(
                status_code=409,
                detail=f"U 位与设备 {label}（U{other.u_start}-{other.u_end}）重叠",
            )


def create_asset(db: Session, operator: User, data: AssetCreate) -> Asset:
    cabinet = _get_cabinet(db, data.cabinet_id)
    ensure_can_manage_cabinet(operator, cabinet)
    _validate_u(db, data.cabinet_id, data.u_start, data.u_end)

    asset = Asset(
        **data.model_dump(),
        in_pool=(data.cabinet_id is None),
        dept_id=settings.dept_id,
    )
    asset.field_source = {
        f: "manual" for f in TRACKED_FIELDS if getattr(asset, f) is not None
    }
    db.add(asset)
    db.flush()
    changelog.log(
        db,
        operator=operator,
        target_type="asset",
        target_id=asset.id,
        cabinet_id=asset.cabinet_id,
        action="create",
    )
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(
    db: Session, operator: User, asset_id: int, data: AssetUpdate, source: str = "manual"
) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="设备不存在")
    ensure_can_manage_cabinet(operator, _get_cabinet(db, asset.cabinet_id))

    changes = data.model_dump(exclude_unset=True)
    # 手动字段保护：非 manual 来源不得覆盖 source=manual 的字段
    applied: dict = {}
    for field, value in changes.items():
        if (
            field in TRACKED_FIELDS
            and source != "manual"
            and asset.field_source.get(field) == "manual"
        ):
            continue
        applied[field] = value

    # 校验变更后的机柜归属与 U 位
    new_cabinet_id = applied.get("cabinet_id", asset.cabinet_id)
    if "cabinet_id" in applied and new_cabinet_id != asset.cabinet_id:
        ensure_can_manage_cabinet(operator, _get_cabinet(db, new_cabinet_id))
    _validate_u(
        db,
        new_cabinet_id,
        applied.get("u_start", asset.u_start),
        applied.get("u_end", asset.u_end),
        exclude_id=asset.id,
    )

    for field, value in applied.items():
        old = getattr(asset, field)
        if old == value:
            continue
        setattr(asset, field, value)
        if field in TRACKED_FIELDS and value is not None:
            asset.field_source = {**asset.field_source, field: source}
        changelog.log(
            db,
            operator=operator,
            target_type="asset",
            target_id=asset.id,
            cabinet_id=asset.cabinet_id,
            action="update",
            field=field,
            old_value=old,
            new_value=value,
            source=source,
        )

    asset.in_pool = asset.cabinet_id is None
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: Session, operator: User, asset_id: int) -> None:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="设备不存在")
    ensure_can_manage_cabinet(operator, _get_cabinet(db, asset.cabinet_id))

    now = datetime.now(timezone.utc)
    asset.deleted_at = now
    for comp in db.query(Component).filter(
        Component.asset_id == asset.id, Component.deleted_at.is_(None)
    ):
        comp.deleted_at = now
    changelog.log(
        db,
        operator=operator,
        target_type="asset",
        target_id=asset.id,
        cabinet_id=asset.cabinet_id,
        action="delete",
    )
    db.commit()


def get_asset(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return asset


def list_assets(
    db: Session,
    *,
    cabinet_id: int | None = None,
    in_pool: bool | None = None,
    asset_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[Asset], int]:
    base = db.query(Asset).filter(Asset.deleted_at.is_(None))
    if cabinet_id is not None:
        base = base.filter(Asset.cabinet_id == cabinet_id)
    if in_pool is not None:
        base = base.filter(Asset.in_pool == in_pool)
    if asset_type:
        base = base.filter(Asset.type == asset_type)
    if status:
        base = base.filter(Asset.status == status)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(
                Asset.sn.ilike(like),
                Asset.asset_tag.ilike(like),
                Asset.ip_inband.ilike(like),
                Asset.bmc_ip.ilike(like),
                Asset.model.ilike(like),
            )
        )
    total = base.count()
    rows = (
        base.outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .add_columns(Cabinet.name, Room.code)
        .order_by(Asset.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = []
    for asset, cabinet_name, room_code in rows:
        asset.cabinet_name = cabinet_name
        asset.room_code = room_code
        items.append(asset)
    return items, total
