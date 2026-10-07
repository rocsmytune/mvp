"""全局搜索（只读）：按关键字跨整机 SN / 部件 SN / 带内 IP / 带外 IP / 资产编号检索。"""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.room import Room
from app.models.user import User

ASSET_SEARCH_FIELDS = ("sn", "asset_tag", "ip_inband", "bmc_ip")


def _matched_field(asset: Asset, q: str) -> str:
    """返回资产上具体命中关键字的字段（多字段命中时按固定顺序取第一个）。"""
    ql = q.strip().lower()
    for field in ASSET_SEARCH_FIELDS:
        value = getattr(asset, field)
        if value and ql in value.lower():
            return field
    return ASSET_SEARCH_FIELDS[0]


def search(db: Session, q: str, limit: int = 50) -> list[dict]:
    """返回命中列表：先资产、后部件，每条带定位信息。"""
    q = q.strip()
    if not q:
        return []
    like = f"%{q}%"
    results: list[dict] = []

    asset_rows = (
        db.query(Asset, Room.code, Cabinet.name, User.name)
        .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Cabinet.owner_id)
        .filter(Asset.deleted_at.is_(None))
        .filter(
            or_(
                Asset.sn.ilike(like),
                Asset.asset_tag.ilike(like),
                Asset.ip_inband.ilike(like),
                Asset.bmc_ip.ilike(like),
            )
        )
        .order_by(Asset.id.desc())
        .limit(limit)
        .all()
    )
    for asset, room_code, cabinet_name, owner_name in asset_rows:
        results.append(
            {
                "kind": "asset",
                "matched_field": _matched_field(asset, q),
                "room_code": room_code,
                "cabinet_id": asset.cabinet_id,
                "cabinet_name": cabinet_name,
                "u_start": asset.u_start,
                "u_end": asset.u_end,
                "owner_name": owner_name,
                "asset_id": asset.id,
                "asset_type": asset.type,
                "asset_sn": asset.sn,
                "asset_tag": asset.asset_tag,
                "model": asset.model,
                "ip_inband": asset.ip_inband,
                "bmc_ip": asset.bmc_ip,
                "status": asset.status,
                "in_pool": asset.in_pool,
                "component_id": None,
                "component_category": None,
                "component_sn": None,
                "component_name": None,
            }
        )

    comp_rows = (
        db.query(Component, Asset, Room.code, Cabinet.name, User.name)
        .join(Asset, Asset.id == Component.asset_id)
        .outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Cabinet.owner_id)
        .filter(Component.deleted_at.is_(None), Asset.deleted_at.is_(None))
        .filter(Component.sn.ilike(like))
        .order_by(Component.id.desc())
        .limit(limit)
        .all()
    )
    for comp, asset, room_code, cabinet_name, owner_name in comp_rows:
        results.append(
            {
                "kind": "component",
                "matched_field": "component_sn",
                "room_code": room_code,
                "cabinet_id": asset.cabinet_id,
                "cabinet_name": cabinet_name,
                "u_start": asset.u_start,
                "u_end": asset.u_end,
                "owner_name": owner_name,
                "asset_id": asset.id,
                "asset_type": asset.type,
                "asset_sn": asset.sn,
                "asset_tag": asset.asset_tag,
                "model": asset.model,
                "ip_inband": asset.ip_inband,
                "bmc_ip": asset.bmc_ip,
                "status": asset.status,
                "in_pool": asset.in_pool,
                "component_id": comp.id,
                "component_category": comp.category,
                "component_sn": comp.sn,
                "component_name": comp.name,
            }
        )

    return results[:limit]
