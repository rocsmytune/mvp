"""部件（Component）业务逻辑。所有写操作在此，统一写 ChangeLog 并做权限校验。"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.user import User
from app.permissions import ensure_can_manage_cabinet
from app.schemas.component import ComponentCreate, ComponentUpdate
from app.services import changelog


def _get_asset(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return asset


def _get_cabinet(db: Session, cabinet_id: int | None) -> Cabinet | None:
    if cabinet_id is None:
        return None
    return db.get(Cabinet, cabinet_id)


def _ensure_can_manage_asset(db: Session, operator: User, asset: Asset) -> None:
    ensure_can_manage_cabinet(operator, _get_cabinet(db, asset.cabinet_id))


def create_component(db: Session, operator: User, data: ComponentCreate) -> Component:
    asset = _get_asset(db, data.asset_id)
    _ensure_can_manage_asset(db, operator, asset)

    comp = Component(**data.model_dump(), dept_id=settings.dept_id)
    db.add(comp)
    db.flush()
    changelog.log(
        db,
        operator=operator,
        target_type="component",
        target_id=comp.id,
        cabinet_id=asset.cabinet_id,
        action="create",
    )
    db.commit()
    db.refresh(comp)
    return comp


def update_component(
    db: Session,
    operator: User,
    component_id: int,
    data: ComponentUpdate,
    source: str = "manual",
) -> Component:
    comp = db.get(Component, component_id)
    if comp is None or comp.deleted_at is not None:
        raise HTTPException(status_code=404, detail="部件不存在")
    asset = _get_asset(db, comp.asset_id)
    _ensure_can_manage_asset(db, operator, asset)

    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        old = getattr(comp, field)
        if old == value:
            continue
        setattr(comp, field, value)
        changelog.log(
            db,
            operator=operator,
            target_type="component",
            target_id=comp.id,
            cabinet_id=asset.cabinet_id,
            action="update",
            field=field,
            old_value=old,
            new_value=value,
            source=source,
        )
    db.commit()
    db.refresh(comp)
    return comp


def delete_component(db: Session, operator: User, component_id: int) -> None:
    comp = db.get(Component, component_id)
    if comp is None or comp.deleted_at is not None:
        raise HTTPException(status_code=404, detail="部件不存在")
    asset = _get_asset(db, comp.asset_id)
    _ensure_can_manage_asset(db, operator, asset)

    comp.deleted_at = datetime.now(timezone.utc)
    changelog.log(
        db,
        operator=operator,
        target_type="component",
        target_id=comp.id,
        cabinet_id=asset.cabinet_id,
        action="delete",
    )
    db.commit()


def list_components(
    db: Session, *, asset_id: int | None = None, skip: int = 0, limit: int = 100
) -> tuple[list[Component], int]:
    query = db.query(Component).filter(Component.deleted_at.is_(None))
    if asset_id is not None:
        query = query.filter(Component.asset_id == asset_id)
    total = query.count()
    items = query.order_by(Component.id.desc()).offset(skip).limit(limit).all()
    return items, total
