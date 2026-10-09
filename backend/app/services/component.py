"""部件（Component）业务逻辑。所有写操作在此，统一写 ChangeLog 并做权限校验。"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.importer.parse import parse_holder
from app.importer.resolve import resolve_holder
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.room import Room
from app.models.user import User
from app.permissions import ensure_can_manage_cabinet
from app.schemas.component import ComponentCreate, ComponentUpdate
from app.services import changelog
from app.services.facets import facet_values


def _contains(col, values: list[str]):
    """文本列「包含」匹配：任一 value 命中即满足（列内 OR）。"""
    return or_(*[col.ilike(f"%{v}%") for v in values])


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


def _resolve_holder(db: Session, raw: str | None) -> tuple[int | None, str | None]:
    """把挂账人输入解析为 (holder_id, holder_name)。复用 importer 的解析与匹配逻辑。

    工号/姓名任意形式均可识别；纯姓名唯一命中也会关联到对应用户。
    """
    if not raw:
        return None, None
    emp_no, name = parse_holder(raw)
    if emp_no is None and name is None:
        return None, None
    holder_id, holder_name, _warning = resolve_holder(db, emp_no, name)
    return holder_id, holder_name


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

    # 跨设备迁移（所在服务器）：校验目标设备存在 + 目标机柜权限，写 asset_id 变更日志。
    current_asset = asset
    new_asset_id = changes.pop("asset_id", None)
    if new_asset_id is not None and new_asset_id != comp.asset_id:
        target_asset = _get_asset(db, new_asset_id)
        _ensure_can_manage_asset(db, operator, target_asset)
        changelog.log(
            db,
            operator=operator,
            target_type="component",
            target_id=comp.id,
            cabinet_id=target_asset.cabinet_id,
            action="update",
            field="asset_id",
            old_value=comp.asset_id,
            new_value=target_asset.id,
            source=source,
        )
        comp.asset_id = target_asset.id
        current_asset = target_asset

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
                cabinet_id=current_asset.cabinet_id,
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
            cabinet_id=current_asset.cabinet_id,
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
    categories: list[str] | None = None,
    sns: list[str] | None = None,
    material_codes: list[str] | None = None,
    holder_names: list[str] | None = None,
    room_codes: list[str] | None = None,
    cabinet_names: list[str] | None = None,
    remarks: list[str] | None = None,
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

    # 多值列筛选（枚举列精确、文本列包含），多列 AND、列内 OR。
    if categories:
        base = base.filter(Component.category.in_(categories))
    if sns:
        base = base.filter(_contains(Component.sn, sns))
    if material_codes:
        base = base.filter(_contains(Component.material_code, material_codes))
    if holder_names:
        base = base.filter(_contains(Component.holder_name, holder_names))
    if remarks:
        base = base.filter(_contains(Component.remark, remarks))
    # 机柜/机房为联表列，经父资产子查询过滤，避免污染下方 outerjoin 的列取用。
    if cabinet_names:
        base = base.filter(
            Component.asset_id.in_(
                db.query(Asset.id)
                .join(Cabinet, Cabinet.id == Asset.cabinet_id)
                .filter(_contains(Cabinet.name, cabinet_names))
            )
        )
    if room_codes:
        base = base.filter(
            Component.asset_id.in_(
                db.query(Asset.id)
                .join(Cabinet, Cabinet.id == Asset.cabinet_id)
                .join(Room, Room.id == Cabinet.room_id)
                .filter(Room.code.in_(room_codes))
            )
        )

    total = base.count()
    rows = (
        base.join(Asset, Asset.id == Component.asset_id)
        .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Component.holder_id)
        .add_columns(
            Asset.sn, Asset.model, Asset.bmc_ip, Asset.cabinet_id, Cabinet.name, Cabinet.owner_id, Room.code, User.employee_no
        )
        .order_by(Component.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = []
    for comp, asset_sn, asset_model, asset_bmc_ip, cabinet_id, cabinet_name, cabinet_owner_id, room_code, holder_employee_no in rows:
        comp.asset_sn = asset_sn
        comp.asset_model = asset_model
        comp.asset_bmc_ip = asset_bmc_ip
        comp.cabinet_id = cabinet_id
        comp.cabinet_name = cabinet_name
        comp.cabinet_owner_id = cabinet_owner_id
        comp.room_code = room_code
        comp.holder_employee_no = holder_employee_no
        items.append(comp)
    return items, total


def list_component_facets(db: Session) -> dict[str, list[dict]]:
    """物料列表各筛选列的去重值 + 计数（未删除部件）。"""
    base = db.query(Component).filter(Component.deleted_at.is_(None))
    loc = base.join(Asset, Asset.id == Component.asset_id).outerjoin(
        Cabinet, Cabinet.id == Asset.cabinet_id
    )
    room = loc.outerjoin(Room, Room.id == Cabinet.room_id)
    return {
        "category": facet_values(base, Component.category),
        "sn": facet_values(base, Component.sn),
        "material_code": facet_values(base, Component.material_code),
        "holder_name": facet_values(base, Component.holder_name),
        "remark": facet_values(base, Component.remark),
        "cabinet_name": facet_values(loc, Cabinet.name),
        "room_code": facet_values(room, Room.code),
    }
