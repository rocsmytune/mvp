"""字典管理业务逻辑。写操作仅系统管理员，禁止删除，统一写 ChangeLog。

字典目前两类：
- asset_status：资产状态（code 为英文枚举，label 为中文展示）
- component_category：部件物料类型（code == label，中文直接入库）

「禁止删除、提示位置」：不提供删除函数；list 返回 usage_count，get_usage 返回
引用该值的资产/部件（含机柜名与 U 位）。
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.dictionary import Dictionary
from app.permissions import require_system_admin
from app.schemas.dictionary import DictionaryCreate, DictionaryUpdate
from app.services import changelog


def _get(db: Session, dict_id: int) -> Dictionary:
    d = db.get(Dictionary, dict_id)
    if d is None:
        raise HTTPException(status_code=404, detail="字典项不存在")
    return d


def _check_unique(
    db: Session, kind: str, code: str, exclude_id: int | None = None
) -> None:
    query = db.query(Dictionary).filter(Dictionary.kind == kind, Dictionary.code == code)
    if exclude_id is not None:
        query = query.filter(Dictionary.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail=f"字典 {kind}/{code} 已存在")


def _usage_count(db: Session, d: Dictionary) -> int:
    if d.kind == "asset_status":
        return (
            db.query(Asset)
            .filter(Asset.status == d.code, Asset.deleted_at.is_(None))
            .count()
        )
    if d.kind == "component_category":
        return (
            db.query(Component)
            .filter(Component.category == d.code, Component.deleted_at.is_(None))
            .count()
        )
    return 0


def list_dictionaries(
    db: Session, *, kind: str | None = None, skip: int = 0, limit: int = 500
) -> tuple[list[dict], int]:
    """读接口开放给所有登录用户（与其它读接口一致），不做角色过滤。"""
    query = db.query(Dictionary)
    if kind:
        query = query.filter(Dictionary.kind == kind)
    total = query.count()
    rows = (
        query.order_by(Dictionary.kind, Dictionary.sort_no, Dictionary.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        {
            "id": d.id,
            "kind": d.kind,
            "code": d.code,
            "label": d.label,
            "sort_no": d.sort_no,
            "usage_count": _usage_count(db, d),
        }
        for d in rows
    ]
    return items, total


def create_dictionary(
    db: Session, operator, data: DictionaryCreate
) -> Dictionary:
    require_system_admin(operator)
    _check_unique(db, data.kind, data.code)

    d = Dictionary(
        kind=data.kind, code=data.code, label=data.label, sort_no=data.sort_no
    )
    db.add(d)
    db.flush()
    changelog.log(
        db, operator=operator, target_type="dictionary", target_id=d.id,
        cabinet_id=None, action="create",
    )
    db.commit()
    db.refresh(d)
    return d


def update_dictionary(
    db: Session, operator, dict_id: int, data: DictionaryUpdate
) -> Dictionary:
    require_system_admin(operator)
    d = _get(db, dict_id)
    changes = data.model_dump(exclude_unset=True)

    if "code" in changes and changes["code"] != d.code:
        _check_unique(db, d.kind, changes["code"], exclude_id=d.id)

    for field, value in changes.items():
        old = getattr(d, field)
        if old == value:
            continue
        setattr(d, field, value)
        changelog.log(
            db, operator=operator, target_type="dictionary", target_id=d.id,
            cabinet_id=None, action="update", field=field,
            old_value=old, new_value=value,
        )
    db.commit()
    db.refresh(d)
    return d


def delete_dictionary(db: Session, operator, dict_id: int) -> None:
    """仅系统管理员可删；被资产/部件引用中的值禁止删除（409 提示使用数）。"""
    require_system_admin(operator)
    d = _get(db, dict_id)
    count = _usage_count(db, d)
    if count > 0:
        raise HTTPException(
            status_code=409, detail=f"该字典值正被 {count} 处使用，无法删除"
        )
    changelog.log(
        db, operator=operator, target_type="dictionary", target_id=d.id,
        cabinet_id=None, action="delete",
    )
    db.delete(d)
    db.commit()


def get_usage(db: Session, dict_id: int) -> list[dict]:
    """返回引用该字典值的资产/部件位置（机柜名 + U 位）。"""
    d = _get(db, dict_id)
    rows: list[dict] = []

    if d.kind == "asset_status":
        pairs = (
            db.query(Asset, Cabinet.name)
            .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
            .filter(Asset.status == d.code, Asset.deleted_at.is_(None))
            .order_by(Cabinet.name, Asset.u_start)
            .all()
        )
        for a, cab_name in pairs:
            rows.append(
                {
                    "target_type": "asset",
                    "sn": a.sn,
                    "asset_sn": None,
                    "name": a.model,
                    "cabinet_name": cab_name,
                    "u_start": a.u_start,
                    "u_end": a.u_end,
                }
            )
    elif d.kind == "component_category":
        triples = (
            db.query(Component, Asset, Cabinet.name)
            .join(Asset, Asset.id == Component.asset_id)
            .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
            .filter(Component.category == d.code, Component.deleted_at.is_(None))
            .order_by(Cabinet.name, Asset.u_start)
            .all()
        )
        for c, a, cab_name in triples:
            rows.append(
                {
                    "target_type": "component",
                    "sn": c.sn,
                    "asset_sn": a.sn,
                    "name": c.model,
                    "cabinet_name": cab_name,
                    "u_start": a.u_start,
                    "u_end": a.u_end,
                }
            )
    return rows
