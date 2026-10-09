"""手工物料表格导入 · 第 2 步：定位与去重（只读，不落库）。

对每个已解析行（ParsedRow）：
1. BMC IP → 资产 → 机柜 → U 位（找不到 → error，提示先补录）
2. 整机SN 与库中不符 → warning
3. 挂账人工号 → users → holder_id / holder_name（匹配不到 → 保留原文）
4. 去重：部件按「物料类型 + SN」找已有；整机/交换机即定位到的资产本身
5. 分类 new / update / error，update 产出字段级变动点（含跨机柜移动）

本模块只做查询与分类，不写库、不改权限；落库与权限校验在提交服务（增量4）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from app.importer.parse import ParsedRow, RowIssue, Severity, Target
from app.models.asset import Asset
from app.models.component import Component
from app.models.user import User


class Action(str, Enum):
    NEW = "new"
    UPDATE = "update"
    NO_CHANGE = "no_change"  # 定位到已有记录且无任何变动点，跳过入库
    ERROR = "error"


@dataclass
class FieldChange:
    field: str
    old: object
    new: object


@dataclass
class ResolvedRow:
    row: ParsedRow
    action: Action
    asset: Asset | None = None              # 定位到的资产（整机/交换机=自身；部件=父机）
    existing_component: Component | None = None
    holder_id: int | None = None            # 挂账人工号解析出的 user.id
    holder_name: str | None = None          # 挂账人姓名（工号匹配→工号对应姓名快照；不匹配→原文）
    changes: list[FieldChange] = field(default_factory=list)
    issues: list[RowIssue] = field(default_factory=list)  # resolve 阶段新增的 error/warning

    @property
    def all_issues(self) -> list[RowIssue]:
        return self.row.issues + self.issues


def resolve_holder(
    db: Session, emp_no: str | None, name: str | None
) -> tuple[int | None, str | None, str | None]:
    """按工号/姓名解析挂账人 → (holder_id, holder_name, warning)。

    - 工号优先：命中 → 关联；姓名与库中不符 → 以工号为准 + 警告；未命中 → 保留原文 + 警告。
    - 纯姓名：唯一命中 → 关联；多个同名 → 保留原文 + 警告；不命中 → 保留原文、无警告。
    """
    if emp_no is None and name is None:
        return None, None, None

    if emp_no is not None:
        user = db.query(User).filter(User.employee_no == emp_no).first()
        if user is not None:
            # 姓名以表格为准（快照）；表格缺姓名时用库中姓名兜底
            resolved_name = name or user.name
            warning = None
            if name and name != user.name:
                warning = (
                    f"挂账人工号 {emp_no} 对应姓名「{user.name}」，与输入「{name}」"
                    "不一致，已按工号关联"
                )
            return user.id, resolved_name, warning
        original = f"{emp_no} {name}".strip() if name else emp_no
        return None, original, f"挂账人工号未匹配到用户：{emp_no}"

    # 纯姓名：按姓名匹配
    users = db.query(User).filter(User.name == name).all()
    if len(users) == 1:
        return users[0].id, users[0].name, None
    if len(users) > 1:
        return (
            None,
            name,
            f"挂账人姓名「{name}」匹配到 {len(users)} 个用户，无法唯一定位，请改用工号",
        )
    return None, name, None


def _resolve_component(
    db: Session,
    row: ParsedRow,
    asset: Asset,
    holder_id: int | None,
    holder_name: str | None,
    issues: list[RowIssue],
) -> ResolvedRow:
    if asset.type != "server":
        issues.append(
            RowIssue(row.row_no, Severity.WARNING, f"部件定位到的资产非服务器类型：{asset.type}")
        )

    matches = (
        db.query(Component)
        .filter(
            Component.category == row.type_or_category,
            Component.sn == row.sn,
            Component.deleted_at.is_(None),
        )
        .order_by(Component.id)
        .all()
    )
    if len(matches) > 1:
        issues.append(
            RowIssue(
                row.row_no,
                Severity.WARNING,
                f"同类型下 SN 重复：库中存在 {len(matches)} 个「{row.type_or_category}」SN {row.sn} 的部件，默认按最早一条更新，请人工确认",
            )
        )

    if not matches:
        return ResolvedRow(
            row=row,
            action=Action.NEW,
            asset=asset,
            holder_id=holder_id,
            holder_name=holder_name,
            issues=issues,
        )

    comp = matches[0]
    changes: list[FieldChange] = []
    # 跨机柜移动：部件从别的资产挂到本次定位的资产下
    if comp.asset_id != asset.id:
        changes.append(FieldChange("asset_id", comp.asset_id, asset.id))

    optional = {"name": row.material_name, "material_code": row.material_code, "remark": row.remark}
    for field, value in optional.items():
        if value is None:
            continue
        old = getattr(comp, field)
        if old != value:
            changes.append(FieldChange(field, old, value))

    # 挂账人：表格提供了工号就按解析结果覆盖（含未匹配到 → 清空 holder_id）
    if row.holder_emp_no is not None:
        for field, value in (("holder_id", holder_id), ("holder_name", holder_name)):
            old = getattr(comp, field)
            if old != value:
                changes.append(FieldChange(field, old, value))

    # 无任何变动点（重复导入且字段完全一致）→ 跳过入库
    if not changes:
        return ResolvedRow(
            row=row,
            action=Action.NO_CHANGE,
            asset=asset,
            existing_component=comp,
            holder_id=holder_id,
            holder_name=holder_name,
            issues=issues,
        )

    return ResolvedRow(
        row=row,
        action=Action.UPDATE,
        asset=asset,
        existing_component=comp,
        holder_id=holder_id,
        holder_name=holder_name,
        changes=changes,
        issues=issues,
    )


def _resolve_asset(
    row: ParsedRow,
    asset: Asset,
    holder_id: int | None,
    holder_name: str | None,
    issues: list[RowIssue],
) -> ResolvedRow:
    changes: list[FieldChange] = []

    if row.sn and row.sn != asset.sn:
        changes.append(FieldChange("sn", asset.sn, row.sn))

    # 挂账人仅交换机落库；服务器整机不挂账
    if row.type_or_category == "switch" and row.holder_emp_no is not None:
        for field, value in (("holder_id", holder_id), ("holder_name", holder_name)):
            old = getattr(asset, field)
            if old != value:
                changes.append(FieldChange(field, old, value))

    return ResolvedRow(
        row=row,
        action=Action.UPDATE if changes else Action.NO_CHANGE,
        asset=asset,
        holder_id=holder_id,
        holder_name=holder_name,
        changes=changes,
        issues=issues,
    )


def resolve_row(db: Session, row: ParsedRow) -> ResolvedRow:
    issues: list[RowIssue] = []

    # parse 阶段已判 error → 不再查库
    if row.has_error:
        return ResolvedRow(row=row, action=Action.ERROR, issues=issues)

    # 1. 定位资产（BMC IP 是定位主键）
    matches = (
        db.query(Asset)
        .filter(Asset.bmc_ip == row.bmc_ip, Asset.deleted_at.is_(None))
        .all()
    )
    if not matches:
        issues.append(
            RowIssue(
                row.row_no,
                Severity.ERROR,
                "BMC IP 未找到对应资产，请先在机柜总览补录机器与 IP",
            )
        )
        return ResolvedRow(row=row, action=Action.ERROR, issues=issues)
    if len(matches) > 1:
        issues.append(
            RowIssue(row.row_no, Severity.ERROR, "BMC IP 对应多个资产，无法唯一定位")
        )
        return ResolvedRow(row=row, action=Action.ERROR, issues=issues)
    asset = matches[0]

    # 2. 整机SN 核对
    if row.machine_sn and asset.sn and row.machine_sn != asset.sn:
        issues.append(
            RowIssue(
                row.row_no,
                Severity.WARNING,
                f"整机SN 与库中不符：库中为 {asset.sn}",
            )
        )

    # 3. 资产类型匹配（整机→server / 交换机→switch）
    if row.target == Target.ASSET and asset.type != row.type_or_category:
        issues.append(
            RowIssue(
                row.row_no,
                Severity.WARNING,
                f"物料类型与定位资产类型不符：库中为 {asset.type}",
            )
        )

    # 4. 挂账人（服务器整机不挂账；部件与交换机落 holder）
    holder_id: int | None = None
    holder_name: str | None = None
    if row.target == Target.COMPONENT or row.type_or_category == "switch":
        holder_id, holder_name, holder_warning = resolve_holder(
            db, row.holder_emp_no, row.holder_name
        )
        if holder_warning:
            issues.append(RowIssue(row.row_no, Severity.WARNING, holder_warning))
    elif row.holder_emp_no is not None:
        issues.append(
            RowIssue(row.row_no, Severity.WARNING, "服务器整机不挂账，挂账人列被忽略")
        )

    # 5. 分类 + 字段级变动点
    if row.target == Target.COMPONENT:
        return _resolve_component(db, row, asset, holder_id, holder_name, issues)
    return _resolve_asset(row, asset, holder_id, holder_name, issues)


def resolve_rows(db: Session, rows: list[ParsedRow]) -> list[ResolvedRow]:
    """批量解析，并在批内做同类型+SN 去重（同批取首行，后续行报错跳过，避免撞唯一索引）。"""
    resolved: list[ResolvedRow] = []
    seen: dict[tuple[str, str], int] = {}
    for row in rows:
        r = resolve_row(db, row)
        # 部件按去重键 (category, sn) 批内去重：首行正常，后续重复行标 error 跳过。
        if r.action != Action.ERROR and row.target == Target.COMPONENT and row.sn:
            key = (row.type_or_category or "", row.sn)
            first = seen.get(key)
            if first is not None:
                r.action = Action.ERROR
                r.existing_component = None
                r.changes = []
                r.issues.append(
                    RowIssue(
                        row.row_no,
                        Severity.ERROR,
                        f"同批内与第 {first} 行物料类型与 SN 重复，跳过（同批取首行）",
                    )
                )
            else:
                seen[key] = row.row_no
        resolved.append(r)
    return resolved
