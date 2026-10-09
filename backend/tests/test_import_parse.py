"""手工物料导入 · 行解析器单元测试（纯函数，无 DB 依赖）。"""

import pytest

from app.importer.parse import (
    Severity,
    Target,
    parse_holder,
    parse_row,
    parse_rows,
    validate_ip,
)


def _row(**overrides) -> dict:
    base = {
        "bmc_ip": "192.0.2.10",
        "machine_sn": "MACHINE-SN-01",
        "material_type": "硬盘",
        "sn": "DISK-SN-01",
        "material_code": "CODE-1",
        "material_name": "测试硬盘",
        "remark": "备注",
        "holder": "900001 测试用户",
    }
    base.update(overrides)
    return base


def _errors(row) -> list[str]:
    return [i.message for i in row.issues if i.severity == Severity.ERROR]


def _warnings(row) -> list[str]:
    return [i.message for i in row.issues if i.severity == Severity.WARNING]


# ---- 物料类型映射 ----


@pytest.mark.parametrize(
    "mt,target,value",
    [
        ("整机", Target.ASSET, "server"),
        ("交换机", Target.ASSET, "switch"),
        ("硬盘", Target.COMPONENT, "硬盘"),
        ("内存", Target.COMPONENT, "内存"),
        ("主板", Target.COMPONENT, "主板"),
        ("光模块", Target.COMPONENT, "光模块"),
        ("RAID", Target.COMPONENT, "RAID"),
        ("网卡", Target.COMPONENT, "网卡"),
        ("BMC插卡", Target.COMPONENT, "BMC插卡"),
    ],
)
def test_material_type_map(mt, target, value):
    row = parse_row(1, _row(material_type=mt))
    assert row.target == target
    assert row.type_or_category == value
    assert not row.has_error


def test_material_type_empty_is_error():
    row = parse_row(1, _row(material_type=""))
    assert row.has_error
    assert any("物料类型为空" in m for m in _errors(row))


def test_material_type_unknown_is_error():
    row = parse_row(1, _row(material_type="磁盘"))
    assert row.has_error
    assert any("无法识别" in m for m in _errors(row))
    # 保留原文供错误信息展示
    assert row.material_type == "磁盘"


# ---- BMC IP ----


def test_bmc_ip_empty_is_error():
    row = parse_row(1, _row(bmc_ip=""))
    assert any("BMC IP 为空" in m for m in _errors(row))


def test_bmc_ip_invalid_is_error():
    row = parse_row(1, _row(bmc_ip="999.999.1.1"))
    assert any("BMC IP 非法" in m for m in _errors(row))


def test_bmc_ip_ipv4_ok():
    assert validate_ip("192.0.2.10")


def test_bmc_ip_ipv6_ok():
    assert validate_ip("2001:db8::1")


# ---- 挂账人 ----


def test_parse_holder_with_name():
    emp, name = parse_holder("900001 测试用户")
    assert emp == "900001"
    assert name == "测试用户"


def test_parse_holder_emp_only():
    emp, name = parse_holder("900001")
    assert emp == "900001"
    assert name is None


def test_parse_holder_empty():
    emp, name = parse_holder("")
    assert emp is None and name is None


def test_parse_holder_extra_whitespace():
    emp, name = parse_holder("  900001   测试 用户  ")
    assert emp == "900001"
    assert name == "测试 用户"  # 首个空白后整体保留，内部空格不动


@pytest.mark.parametrize(
    "raw,emp,name",
    [
        ("900002 测试用户", "900002", "测试用户"),   # 工号在前 + 空格
        ("900002测试用户", "900002", "测试用户"),    # 工号在前 + 紧贴
        ("测试用户 900002", "900002", "测试用户"),   # 姓名在前 + 空格
        ("测试用户900002", "900002", "测试用户"),    # 姓名在前 + 紧贴
        ("900002", "900002", None),                  # 纯工号
        ("测试用户", None, "测试用户"),              # 纯姓名
    ],
)
def test_parse_holder_formats(raw, emp, name):
    assert parse_holder(raw) == (emp, name)


def test_holder_flows_into_row():
    row = parse_row(1, _row(holder="900001 张三"))
    assert row.holder_emp_no == "900001"
    assert row.holder_name == "张三"


# ---- SN 规则 ----


def test_component_sn_empty_is_error():
    row = parse_row(1, _row(sn="", material_type="硬盘"))
    assert any("部件 SN 为空" in m for m in _errors(row))


def test_server_sn_empty_is_warning_not_error():
    row = parse_row(1, _row(sn="", material_type="整机"))
    assert not row.has_error
    assert any("SN 为空" in m for m in _warnings(row))


def test_switch_sn_empty_is_warning_not_error():
    row = parse_row(1, _row(sn="", material_type="交换机"))
    assert not row.has_error
    assert any("SN 为空" in m for m in _warnings(row))


def test_asset_sn_machine_sn_mismatch_warning():
    row = parse_row(1, _row(material_type="整机", sn="SN-A", machine_sn="SN-B"))
    assert not row.has_error
    assert any("应一致" in m for m in _warnings(row))


def test_asset_sn_machine_sn_match_no_warning():
    row = parse_row(1, _row(material_type="交换机", sn="SN-A", machine_sn="SN-A"))
    assert not any("应一致" in m for m in _warnings(row))


def test_component_sn_machine_sn_can_differ():
    # 部件行 SN 是部件自身，整机SN 是父机，允许不同
    row = parse_row(1, _row(material_type="硬盘", sn="DISK-1", machine_sn="MACHINE-1"))
    assert not any("应一致" in m for m in _warnings(row))


# ---- 字段清洗 / 批量 ----


def test_fields_are_stripped():
    row = parse_row(1, _row(material_type="  硬盘  ", sn="  SN-1  "))
    assert row.material_type == "硬盘"
    assert row.sn == "SN-1"


def test_valid_component_row_has_no_issues():
    row = parse_row(1, _row())
    assert row.issues == []
    assert not row.has_error


def test_parse_rows_numbering_and_mixed():
    rows = parse_rows([_row(), _row(material_type="坏类型")])
    assert rows[0].row_no == 1 and not rows[0].has_error
    assert rows[1].row_no == 2 and rows[1].has_error
