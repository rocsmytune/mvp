"""导入提交服务：预览（解析+定位+落批次）与确认入库。

所有写操作在此，统一写 ChangeLog 并做权限校验：
- 管理员：导入全部；
- 柜主：只能导入定位到 owner 为自己的机柜（跨柜移动还需源机柜权限）；
- 成员：不允许导入（confirm 直接 403）。
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.importer.parse import Severity, parse_rows
from app.importer.resolve import Action, ResolvedRow, resolve_rows
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.import_batch import ImportBatch
from app.models.user import User
from app.permissions import ADMIN_ROLES, ROLE_MEMBER, can_manage_cabinet
from app.services import changelog


def _summary(resolved: list[ResolvedRow]) -> dict:
    counts = {"new": 0, "update": 0, "no_change": 0, "error": 0, "warning": 0}
    for r in resolved:
        if r.action == Action.ERROR:
            counts["error"] += 1
        elif r.action == Action.NEW:
            counts["new"] += 1
        elif r.action == Action.NO_CHANGE:
            counts["no_change"] += 1
        else:
            counts["update"] += 1
        if any(i.severity == Severity.WARNING for i in r.all_issues):
            counts["warning"] += 1
    counts["total"] = len(resolved)
    return counts


def _to_str(value: object) -> str | None:
    return None if value is None else str(value)


def _serialize_preview(db: Session, resolved: list[ResolvedRow]) -> list[dict]:
    cabinet_ids = {
        r.asset.cabinet_id
        for r in resolved
        if r.asset is not None and r.asset.cabinet_id is not None
    }
    cabinets = (
        {c.id: c for c in db.query(Cabinet).filter(Cabinet.id.in_(cabinet_ids)).all()}
        if cabinet_ids
        else {}
    )
    rows: list[dict] = []
    for r in resolved:
        asset = r.asset
        cabinet_name = None
        if asset is not None and asset.cabinet_id is not None:
            cab = cabinets.get(asset.cabinet_id)
            cabinet_name = cab.name if cab is not None else None
        rows.append(
            {
                "row_no": r.row.row_no,
                "action": r.action.value,
                "material_type": r.row.material_type,
                "sn": r.row.sn,
                "bmc_ip": r.row.bmc_ip,
                "machine_sn": r.row.machine_sn,
                "asset_id": asset.id if asset else None,
                "asset_sn": asset.sn if asset else None,
                "cabinet_name": cabinet_name,
                "u_start": asset.u_start if asset else None,
                "u_end": asset.u_end if asset else None,
                "holder_name": r.holder_name,
                "changes": [
                    {"field": c.field, "old": _to_str(c.old), "new": _to_str(c.new)}
                    for c in r.changes
                ],
                "issues": [
                    {"severity": i.severity.value, "message": i.message}
                    for i in r.all_issues
                ],
            }
        )
    return rows


def preview(
    db: Session, operator: User, file_name: str | None, rows: list[dict]
) -> dict:
    if operator.role == ROLE_MEMBER:
        raise HTTPException(status_code=403, detail="成员不允许导入")
    parsed = parse_rows(rows)
    resolved = resolve_rows(db, parsed)
    # 先序列化（对象仍新鲜），再落批次，避免 commit 后 ORM 对象过期
    preview_rows = _serialize_preview(db, resolved)
    summary = _summary(resolved)
    batch = ImportBatch(
        file_name=file_name,
        operator_id=operator.id,
        status="previewed",
        summary_json={"rows": rows, "summary": summary},
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {
        "batch_id": batch.id,
        "file_name": file_name,
        "summary": summary,
        "rows": preview_rows,
    }


def _create_component(db: Session, operator: User, r: ResolvedRow, batch_id: int) -> None:
    comp = Component(
        asset_id=r.asset.id,
        category=r.row.type_or_category,
        sn=r.row.sn,
        name=r.row.material_name,
        material_code=r.row.material_code,
        remark=r.row.remark,
        holder_id=r.holder_id,
        holder_name=r.holder_name,
        sn_source="import",
        dept_id=settings.dept_id,
    )
    db.add(comp)
    db.flush()
    changelog.log(
        db,
        operator=operator,
        target_type="component",
        target_id=comp.id,
        cabinet_id=r.asset.cabinet_id,
        action="create",
        source="import",
        batch_id=batch_id,
    )


def _apply_changes(
    db: Session, operator: User, r: ResolvedRow, batch_id: int
) -> list[str]:
    """把字段级变动点落库并写 ChangeLog；返回被 manual 保护而跳过的字段名。"""
    is_component = r.existing_component is not None
    target = r.existing_component if is_component else r.asset
    target_type = "component" if is_component else "asset"

    skipped: list[str] = []
    for ch in r.changes:
        # 规则6：资产关键字段 source=manual 时不被 import 覆盖
        if (
            target_type == "asset"
            and ch.field == "sn"
            and (target.field_source or {}).get("sn") == "manual"
        ):
            skipped.append("sn")
            continue
        setattr(target, ch.field, ch.new)
        if target_type == "asset" and ch.field == "sn":
            target.field_source = {**(target.field_source or {}), "sn": "import"}
        changelog.log(
            db,
            operator=operator,
            target_type=target_type,
            target_id=target.id,
            cabinet_id=r.asset.cabinet_id,
            action="update",
            field=ch.field,
            old_value=ch.old,
            new_value=ch.new,
            source="import",
            batch_id=batch_id,
        )
    return skipped


def _commit_row(db: Session, operator: User, r: ResolvedRow, batch_id: int) -> dict:
    row_no = r.row.row_no
    if r.action == Action.ERROR:
        msg = "；".join(i.message for i in r.all_issues)
        return {
            "row_no": row_no,
            "action": r.action.value,
            "result": "skipped",
            "message": msg,
        }

    # 无变动点：重复导入且字段完全一致，跳过，不产生无意义更新。
    if r.action == Action.NO_CHANGE:
        return {
            "row_no": row_no,
            "action": r.action.value,
            "result": "skipped",
            "message": "无变化，跳过",
        }

    target_cabinet = (
        db.get(Cabinet, r.asset.cabinet_id) if r.asset.cabinet_id is not None else None
    )
    if not can_manage_cabinet(operator, target_cabinet):
        return {
            "row_no": row_no,
            "action": r.action.value,
            "result": "skipped",
            "message": "无权导入该机柜",
        }

    # 跨柜移动：源机柜也需权限
    if r.existing_component is not None and r.existing_component.asset_id != r.asset.id:
        src_asset = db.get(Asset, r.existing_component.asset_id)
        src_cabinet = (
            db.get(Cabinet, src_asset.cabinet_id)
            if src_asset is not None and src_asset.cabinet_id is not None
            else None
        )
        if not can_manage_cabinet(operator, src_cabinet):
            return {
                "row_no": row_no,
                "action": r.action.value,
                "result": "skipped",
                "message": "无权移动该部件（原机柜无权限）",
            }

    if r.action == Action.NEW:
        _create_component(db, operator, r, batch_id)
        return {"row_no": row_no, "action": r.action.value, "result": "created"}

    skipped = _apply_changes(db, operator, r, batch_id)
    message = None
    if skipped:
        message = "部分字段未覆盖（manual 来源）：" + "、".join(skipped)
    return {
        "row_no": row_no,
        "action": r.action.value,
        "result": "updated",
        "message": message,
    }


def commit(db: Session, operator: User, batch_id: int) -> dict:
    if operator.role == ROLE_MEMBER:
        raise HTTPException(status_code=403, detail="成员不允许导入")

    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="导入批次不存在")
    if batch.status != "previewed":
        raise HTTPException(status_code=409, detail="该批次已处理，不能重复入库")

    raw_rows = (batch.summary_json or {}).get("rows", [])
    resolved = resolve_rows(db, parse_rows(raw_rows))

    rows = [_commit_row(db, operator, r, batch.id) for r in resolved]
    created = sum(1 for r in rows if r["result"] == "created")
    updated = sum(1 for r in rows if r["result"] == "updated")
    skipped = sum(1 for r in rows if r["result"] == "skipped")

    batch.status = "committed"
    batch.summary_json = {
        **(batch.summary_json or {}),
        "result": {"created": created, "updated": updated, "skipped": skipped},
    }
    db.commit()

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "summary": {
            "total": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
        },
        "rows": rows,
    }


def list_batches(db: Session, operator: User) -> tuple[list[ImportBatch], int]:
    query = db.query(ImportBatch)
    if operator.role not in ADMIN_ROLES:
        query = query.filter(ImportBatch.operator_id == operator.id)
    total = query.count()
    items = query.order_by(ImportBatch.id.desc()).limit(100).all()
    return items, total
