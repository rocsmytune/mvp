"""部件（Component）业务逻辑。所有写操作在此，统一写 ChangeLog 并做权限校验。"""

import re
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


# 挂账人「工号 姓名」：本系统工号为纯数字，姓名可为中英文等任意内容。
_HOLDER_RE = re.compile(r"^(\d+)(?:\s+(.+))?$")


def _resolve_holder(db: Session, raw: str | None) -> tuple[int | None, str | None]:
    """把挂账人输入「工号 姓名」解析为 (holder_id, holder_name)。

    工号命中 users → (user.id, 姓名快照或库中姓名)；工号未命中或纯姓名 → 存原文、holder_id 为空。
    """
    if not raw:
        return None, None
    text = raw.strip()
    m = _HOLDER_RE.match(text)
    if m:
        emp_no, name = m.group(1), m.group(2)
        user = db.query(User).filter(User.employee_no == emp_no).first()
        if user is not None:
            return user.id, (name or user.name)
    return None, text


def create_component(db: Session, operator: User, data: ComponentCreate) -> Component:
    asset = _get_asset(db, data.asset_id)
    _ensure_can_manage_asset(db, operator, asset)

    payload = data.model_dump()
    holder_id, holder_name = _resolve_holder(db, payload.pop("holder_name", None))
    comp = Component(
        **payload, holder_id=holder_id, holder_name=holder_name, dept_id=settings.dept_id
    )
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

    # 挂账人单独解析：把「工号 姓名」拆成 holder_id + holder_name 一并落库。
    if "holder_name" in changes:
        holder_id, holder_name = _resolve_holder(db, changes.pop("holder_name"))
        for field, value in (("holder_id", holder_id), ("holder_name", holder_name)):
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
    db: Session,
    *,
    asset_id: int | None = None,
    category: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Component], int]:
    base = db.query(Component).filter(Component.deleted_at.is_(None))
    if asset_id is not None:
        base = base.filter(Component.asset_id == asset_id)
    if category:
        base = base.filter(Component.category == category)
    if q:
        like = f"%{q}%"
        base = base.filter(
            or_(
                Component.sn.ilike(like),
                Component.model.ilike(like),
                Component.name.ilike(like),
                Component.material_code.ilike(like),
            )
        )
    total = base.count()
    rows = (
        base.join(Asset, Asset.id == Component.asset_id)
        .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Component.holder_id)
        .add_columns(
            Asset.sn, Asset.model, Asset.cabinet_id, Cabinet.name, Room.code, User.employee_no
        )
        .order_by(Component.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = []
    for comp, asset_sn, asset_model, cabinet_id, cabinet_name, room_code, holder_employee_no in rows:
        comp.asset_sn = asset_sn
        comp.asset_model = asset_model
        comp.cabinet_id = cabinet_id
        comp.cabinet_name = cabinet_name
        comp.room_code = room_code
        comp.holder_employee_no = holder_employee_no
        items.append(comp)
    return items, total
