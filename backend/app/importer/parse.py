"""手工物料表格导入 · 第 1 步：行解析（纯函数，不碰数据库）。

把上传的 8 列原始行解析为结构化 ParsedRow，并产出行级 error / warning。
定位（BMC IP → 资产）、挂账人工号匹配、去重等需要查库的步骤在 resolve.py，
本模块只做「格式与取值」层面的校验，方便单测且不依赖 ORM。

表格列（顺序）：BMC IP / 整机SN / 物料类型 / SN / 物料编码 / 物料名称 / 备注 / 挂账人。
内部键名：bmc_ip / machine_sn / material_type / sn / material_code / material_name / remark / holder。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import ip_address


class Severity(str, Enum):
    ERROR = "error"      # 整行不入库
    WARNING = "warning"  # 可入库，预览时标记


class Target(str, Enum):
    ASSET = "asset"
    COMPONENT = "component"


@dataclass
class RowIssue:
    row_no: int
    severity: Severity
    message: str


@dataclass
class ParsedRow:
    row_no: int
    bmc_ip: str | None
    machine_sn: str | None
    material_type: str | None       # 归一化后的物料类型原文；空/无法识别时保留原值
    target: Target | None           # asset / component
    type_or_category: str | None    # asset: "server"/"switch"；component: 中文 category
    sn: str | None
    material_code: str | None
    material_name: str | None
    remark: str | None
    holder_emp_no: str | None       # 挂账人工号（纯数字，可在姓名前或后）
    holder_name: str | None         # 挂账人姓名（非数字部分），resolve 阶段兜底
    issues: list[RowIssue] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(i.severity == Severity.ERROR for i in self.issues)


# 9 种物料类型 → (target, type 或 category)。整机/交换机=资产本身，其余 7 类=部件。
MATERIAL_TYPE_MAP: dict[str, tuple[Target, str]] = {
    "整机": (Target.ASSET, "server"),
    "交换机": (Target.ASSET, "switch"),
    "硬盘": (Target.COMPONENT, "硬盘"),
    "内存": (Target.COMPONENT, "内存"),
    "主板": (Target.COMPONENT, "主板"),
    "光模块": (Target.COMPONENT, "光模块"),
    "RAID": (Target.COMPONENT, "RAID"),
    "网卡": (Target.COMPONENT, "网卡"),
    "BMC插卡": (Target.COMPONENT, "BMC插卡"),
}

# 部件类型：SN 是去重主键，缺 SN 视为错误（整机/交换机靠 BMC IP 定位，缺 SN 仅警告）。
COMPONENT_TYPES = {
    t for t, (target, _) in MATERIAL_TYPE_MAP.items() if target == Target.COMPONENT
}


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_holder(raw: object) -> tuple[str | None, str | None]:
    """拆「挂账人」→ (工号, 姓名)。工号=纯数字，姓名=其余非数字部分。

    支持多种书写形式：
    - 「00886677 石铭哲」/「00886677石铭哲」  工号在前（可空格分隔或紧贴）
    - 「石铭哲 00886677」/「石铭哲00886677」  姓名在前
    - 「00886677」→ (工号, None)
    - 「石铭哲」  → (None, 姓名)
    """
    text = _clean(raw)
    if not text:
        return None, None

    # 工号在前：数字开头，后接（可空）姓名
    m = re.match(r"^(\d+)\s*(.*)$", text)
    if m:
        return m.group(1), _clean(m.group(2))

    # 姓名在前：结尾是纯数字工号
    m = re.match(r"^(.*?)\s*(\d+)$", text)
    if m:
        return m.group(2), _clean(m.group(1))

    # 纯姓名
    return None, text


def validate_ip(raw: object) -> bool:
    text = _clean(raw)
    if not text:
        return False
    try:
        ip_address(text)
        return True
    except ValueError:
        return False


def parse_row(row_no: int, row: dict) -> ParsedRow:
    issues: list[RowIssue] = []

    bmc_ip = _clean(row.get("bmc_ip"))
    machine_sn = _clean(row.get("machine_sn"))
    material_type = _clean(row.get("material_type"))
    sn = _clean(row.get("sn"))
    material_code = _clean(row.get("material_code"))
    material_name = _clean(row.get("material_name"))
    remark = _clean(row.get("remark"))
    holder_emp_no, holder_name = parse_holder(row.get("holder"))

    # 物料类型 → target / type_or_category
    target: Target | None = None
    type_or_category: str | None = None
    if not material_type:
        issues.append(RowIssue(row_no, Severity.ERROR, "物料类型为空"))
    else:
        mapped = MATERIAL_TYPE_MAP.get(material_type)
        if mapped is None:
            issues.append(
                RowIssue(row_no, Severity.ERROR, f"物料类型无法识别：{material_type}")
            )
        else:
            target, type_or_category = mapped

    # BMC IP：定位主键，缺失或非法 → 整行无法定位
    if not bmc_ip:
        issues.append(RowIssue(row_no, Severity.ERROR, "BMC IP 为空"))
    elif not validate_ip(bmc_ip):
        issues.append(RowIssue(row_no, Severity.ERROR, f"BMC IP 非法：{bmc_ip}"))

    # SN：部件靠 SN 去重（空 → 错误）；整机/交换机靠 BMC IP 定位（空 → 警告）
    if not sn:
        if target == Target.COMPONENT:
            issues.append(RowIssue(row_no, Severity.ERROR, "部件 SN 为空"))
        elif target == Target.ASSET:
            issues.append(
                RowIssue(row_no, Severity.WARNING, "整机/交换机 SN 为空（仍按 BMC IP 定位）")
            )

    # 整机/交换机行：SN 列与整机SN 列指向同一资产，应一致（服务器/交换机本身无物料编码，就是机框）
    if target == Target.ASSET and sn and machine_sn and sn != machine_sn:
        issues.append(
            RowIssue(row_no, Severity.WARNING, "整机/交换机行的 SN 与整机SN 应一致")
        )

    return ParsedRow(
        row_no=row_no,
        bmc_ip=bmc_ip,
        machine_sn=machine_sn,
        material_type=material_type,
        target=target,
        type_or_category=type_or_category,
        sn=sn,
        material_code=material_code,
        material_name=material_name,
        remark=remark,
        holder_emp_no=holder_emp_no,
        holder_name=holder_name,
        issues=issues,
    )


def parse_rows(rows: list[dict]) -> list[ParsedRow]:
    """批量解析，行号从 1 开始（对应 Excel 数据行）。"""
    return [parse_row(i, row) for i, row in enumerate(rows, start=1)]
