"""导出备份：机柜 / 资产 / 部件三层扁平化，只读，admin 专属。

恢复方式为「仅导出」——导出完整、自描述、以业务键（机房编码 / 机柜名 /
BMC IP / 工号）关联的表格，由管理员在新平台上手工重建，不做反向导入。
"""

from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.room import Room
from app.models.user import User

TYPE_LABEL = {"server": "整机", "switch": "交换机"}


def get_snapshot(db: Session) -> dict:
    cabinets = (
        db.query(Cabinet)
        .filter(Cabinet.deleted_at.is_(None))
        .order_by(Cabinet.id)
        .all()
    )
    assets = (
        db.query(Asset).filter(Asset.deleted_at.is_(None)).order_by(Asset.id).all()
    )
    components = (
        db.query(Component)
        .filter(Component.deleted_at.is_(None))
        .order_by(Component.id)
        .all()
    )

    room_by_id = {
        r.id: r for r in db.query(Room).filter(Room.deleted_at.is_(None)).all()
    }
    cabinet_by_id = {c.id: c for c in cabinets}
    user_by_id = {u.id: u for u in db.query(User).all()}
    asset_by_id = {a.id: a for a in assets}

    cab_out = []
    for c in cabinets:
        room = room_by_id.get(c.room_id)
        owner = user_by_id.get(c.owner_id) if c.owner_id else None
        cab_out.append(
            {
                "room_code": room.code if room else None,
                "name": c.name,
                "total_u": c.total_u,
                "owner_employee_no": owner.employee_no if owner else None,
                "owner_name": owner.name if owner else None,
            }
        )

    asset_out = []
    for a in assets:
        cab = cabinet_by_id.get(a.cabinet_id)
        room = room_by_id.get(cab.room_id) if cab else None
        holder = user_by_id.get(a.holder_id) if a.holder_id else None
        asset_out.append(
            {
                "room_code": room.code if room else None,
                "cabinet_name": cab.name if cab else None,
                "type": TYPE_LABEL.get(a.type, a.type),
                "u_start": a.u_start,
                "u_end": a.u_end,
                "sn": a.sn,
                "asset_tag": a.asset_tag,
                "model": a.model,
                "cpu_model": a.cpu_model,
                "ip_inband": a.ip_inband,
                "bmc_ip": a.bmc_ip,
                "status": a.status,
                "holder_employee_no": holder.employee_no if holder else None,
                "holder_name": holder.name if holder else None,
                "remark": a.remark,
            }
        )

    comp_out = []
    for comp in components:
        asset = asset_by_id.get(comp.asset_id)
        holder = user_by_id.get(comp.holder_id) if comp.holder_id else None
        # 挂账人合成「工号 姓名」（与导入格式一致）；未匹配时 holder_name 已是原文。
        holder_str = (
            f"{holder.employee_no} {holder.name}" if holder else comp.holder_name
        )
        comp_out.append(
            {
                "bmc_ip": asset.bmc_ip if asset else None,
                "machine_sn": asset.sn if asset else None,
                "material_type": comp.category,
                "sn": comp.sn,
                "material_code": comp.material_code,
                "material_name": comp.name,
                "remark": comp.remark,
                "holder": holder_str,
            }
        )

    return {"cabinets": cab_out, "assets": asset_out, "components": comp_out}
