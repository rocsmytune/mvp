"""手工物料导入 · 定位与去重（resolve）测试。只读，不落库；用例内自建/自清数据。"""

import pytest

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.importer.parse import parse_row
from app.importer.resolve import Action, resolve_row, resolve_rows
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.component import Component
from app.models.room import Room
from app.models.user import User

HOLDER_NO = "900010"  # 与 conftest 的 test_user(900001) 区分，避免冲突


@pytest.fixture
def resolve_env():
    db = SessionLocal()

    def _purge():
        db.query(Component).filter(Component.sn.like("T-IMP-%")).delete(
            synchronize_session=False
        )
        db.query(Asset).filter(Asset.sn.like("T-IMP-%")).delete(synchronize_session=False)
        db.query(Cabinet).filter(Cabinet.name.like("T-IMP-%")).delete(
            synchronize_session=False
        )
        db.query(Room).filter(Room.code.like("T-IMP-%")).delete(synchronize_session=False)
        db.query(User).filter(User.employee_no == HOLDER_NO).delete(synchronize_session=False)
        db.commit()

    _purge()  # 清残留
    try:
        holder = User(
            employee_no=HOLDER_NO,
            name="测试挂账人",
            role="member",
            password_hash=hash_password("x"),
        )
        db.add(holder)
        room = Room(city="测试市", code="T-IMP-ROOM", zone="测试区")
        db.add(room)
        db.flush()
        cabinet = Cabinet(room_id=room.id, name="T-IMP-01", total_u=45)
        db.add(cabinet)
        db.flush()
        server = Asset(
            type="server",
            cabinet_id=cabinet.id,
            u_start=1,
            u_end=2,
            sn="T-IMP-SERVER-01",
            bmc_ip="192.0.2.10",
        )
        db.add(server)
        db.commit()
        db.refresh(holder)
        db.refresh(server)
        db.refresh(cabinet)
        yield {"db": db, "holder": holder, "server": server, "cabinet": cabinet}
    finally:
        _purge()
        db.close()


def _parsed(**overrides) -> object:
    base = {
        "bmc_ip": "192.0.2.10",
        "machine_sn": "T-IMP-SERVER-01",
        "material_type": "硬盘",
        "sn": "T-IMP-COMP-01",
        "material_code": "CODE-1",
        "material_name": "测试硬盘",
        "remark": "",
        "holder": "900010 测试挂账人",
    }
    base.update(overrides)
    return parse_row(1, base)


def _add_asset(db, *, cabinet_id, type, sn, bmc_ip, u_start, u_end):
    a = Asset(
        type=type, cabinet_id=cabinet_id, u_start=u_start, u_end=u_end,
        sn=sn, bmc_ip=bmc_ip,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ---- 定位 ----


def test_bmc_ip_not_found_is_error(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(bmc_ip="192.0.2.99"))
    assert res.action is Action.ERROR
    assert any("未找到对应资产" in i.message for i in res.issues)


def test_bmc_ip_multiple_is_error(resolve_env):
    db = resolve_env["db"]
    _add_asset(
        db, cabinet_id=resolve_env["cabinet"].id, type="server",
        sn="T-IMP-SERVER-02", bmc_ip="192.0.2.10", u_start=5, u_end=6,
    )
    res = resolve_row(db, _parsed(holder=""))
    assert res.action is Action.ERROR
    assert any("多个资产" in i.message for i in res.issues)


def test_parse_error_skips_resolve(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(material_type="坏类型", bmc_ip="192.0.2.99"))
    assert res.action is Action.ERROR
    assert res.asset is None
    assert any("无法识别" in i.message for i in res.all_issues)
    # 未进入 DB 定位，不应出现「未找到」报错
    assert not any("未找到" in i.message for i in res.all_issues)


# ---- 整机SN 核对 ----


def test_machine_sn_mismatch_warning(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(machine_sn="OTHER-SN", holder=""))
    assert res.action is Action.NEW
    assert any("整机SN 与库中不符" in i.message for i in res.issues)


def test_machine_sn_match_no_warning(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(machine_sn="T-IMP-SERVER-01", holder=""))
    assert not any("整机SN 与库中不符" in i.message for i in res.issues)


# ---- 挂账人 ----


def test_holder_matched(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="900010 测试挂账人"))
    assert res.holder_id == resolve_env["holder"].id
    assert res.holder_name == "测试挂账人"


def test_holder_unmatched_warning(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="999999 张三"))
    assert res.holder_id is None
    assert res.holder_name == "999999 张三"
    assert any("未匹配到用户" in i.message for i in res.issues)


def test_holder_name_only_matches(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="测试挂账人"))
    assert res.holder_id == resolve_env["holder"].id
    assert res.holder_name == "测试挂账人"


def test_holder_name_only_multiple_warning(resolve_env):
    db = resolve_env["db"]
    dup = User(
        employee_no="900011", name="测试挂账人", role="member",
        password_hash=hash_password("x"),
    )
    db.add(dup)
    db.commit()
    try:
        res = resolve_row(db, _parsed(holder="测试挂账人"))
        assert res.holder_id is None
        assert res.holder_name == "测试挂账人"
        assert any("无法唯一定位" in i.message for i in res.issues)
    finally:
        db.query(User).filter(User.employee_no == "900011").delete(
            synchronize_session=False
        )
        db.commit()


def test_holder_emp_no_with_mismatched_name_warning(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="900010 错误姓名"))
    assert res.holder_id == resolve_env["holder"].id
    assert res.holder_name == "错误姓名"
    assert any("不一致" in i.message for i in res.issues)


def test_holder_format_emp_first_no_space(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="900010测试挂账人"))
    assert res.holder_id == resolve_env["holder"].id
    assert res.holder_name == "测试挂账人"


def test_holder_format_name_first(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder="测试挂账人900010"))
    assert res.holder_id == resolve_env["holder"].id
    assert res.holder_name == "测试挂账人"


# ---- 部件去重 / 变动点 ----


def test_component_new(resolve_env):
    res = resolve_row(resolve_env["db"], _parsed(holder=""))
    assert res.action is Action.NEW
    assert res.existing_component is None
    assert res.asset.id == resolve_env["server"].id


def test_component_update_field_diff(resolve_env):
    db = resolve_env["db"]
    comp = Component(
        asset_id=resolve_env["server"].id, category="硬盘", sn="T-IMP-COMP-01",
        name="旧名称", material_code="OLD-CODE",
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)

    res = resolve_row(db, _parsed(material_name="新名称", material_code="NEW-CODE", holder=""))
    assert res.action is Action.UPDATE
    assert res.existing_component.id == comp.id
    fields = {c.field: c for c in res.changes}
    assert set(fields) == {"name", "material_code"}
    assert fields["name"].old == "旧名称" and fields["name"].new == "新名称"
    assert fields["material_code"].old == "OLD-CODE" and fields["material_code"].new == "NEW-CODE"


def test_component_move_cross_cabinet(resolve_env):
    db = resolve_env["db"]
    room2 = Room(city="测试市", code="T-IMP-ROOM-2", zone="测试区")
    db.add(room2)
    db.flush()
    cab2 = Cabinet(room_id=room2.id, name="T-IMP-02", total_u=45)
    db.add(cab2)
    db.flush()
    server2 = _add_asset(
        db, cabinet_id=cab2.id, type="server",
        sn="T-IMP-SERVER-02", bmc_ip="192.0.2.20", u_start=1, u_end=2,
    )
    comp = Component(asset_id=server2.id, category="硬盘", sn="T-IMP-COMP-01")
    db.add(comp)
    db.commit()
    db.refresh(comp)

    # bmc_ip 指向第一个服务器，但 SN 相同的部件挂在第二个服务器 → 跨机柜移动
    res = resolve_row(db, _parsed(holder=""))
    assert res.action is Action.UPDATE
    fields = {c.field: c for c in res.changes}
    assert fields["asset_id"].old == server2.id
    assert fields["asset_id"].new == resolve_env["server"].id


def test_component_sn_duplicate_warning(resolve_env):
    db = resolve_env["db"]
    db.add_all(
        [
            Component(asset_id=resolve_env["server"].id, category="硬盘", sn="T-IMP-COMP-01"),
            Component(asset_id=resolve_env["server"].id, category="硬盘", sn="T-IMP-COMP-01"),
        ]
    )
    db.commit()
    res = resolve_row(db, _parsed(holder=""))
    assert res.action is Action.UPDATE
    assert any("SN 重复" in i.message for i in res.issues)


# ---- 整机 / 交换机（资产本身）----


def test_server_sn_update(resolve_env):
    res = resolve_row(
        resolve_env["db"],
        _parsed(material_type="整机", sn="T-IMP-SERVER-01-NEW", machine_sn="", holder=""),
    )
    assert res.action is Action.UPDATE
    fields = {c.field: c for c in res.changes}
    assert fields["sn"].old == "T-IMP-SERVER-01"
    assert fields["sn"].new == "T-IMP-SERVER-01-NEW"


def test_server_ignores_holder(resolve_env):
    res = resolve_row(
        resolve_env["db"],
        _parsed(material_type="整机", sn="T-IMP-SERVER-01", holder="900010 测试挂账人"),
    )
    assert res.action is Action.UPDATE
    assert any("不挂账" in i.message for i in res.issues)
    assert res.holder_id is None
    assert all(c.field not in ("holder_id", "holder_name") for c in res.changes)


def test_switch_holder_update(resolve_env):
    db = resolve_env["db"]
    sw = _add_asset(
        db, cabinet_id=resolve_env["cabinet"].id, type="switch",
        sn="T-IMP-SWITCH-01", bmc_ip="192.0.2.30", u_start=3, u_end=3,
    )
    res = resolve_row(
        db,
        _parsed(
            material_type="交换机", bmc_ip="192.0.2.30",
            sn="T-IMP-SWITCH-01", machine_sn="T-IMP-SWITCH-01",
            holder="900010 测试挂账人",
        ),
    )
    assert res.action is Action.UPDATE
    fields = {c.field: c for c in res.changes}
    assert fields["holder_id"].new == resolve_env["holder"].id
    assert fields["holder_name"].new == "测试挂账人"


def test_asset_type_mismatch_warning(resolve_env):
    db = resolve_env["db"]
    _add_asset(
        db, cabinet_id=resolve_env["cabinet"].id, type="switch",
        sn="T-IMP-SWITCH-01", bmc_ip="192.0.2.30", u_start=3, u_end=3,
    )
    res = resolve_row(
        db, _parsed(material_type="整机", bmc_ip="192.0.2.30", sn="", machine_sn="", holder="")
    )
    assert res.action is Action.UPDATE
    assert any("类型不符" in i.message for i in res.issues)


# ---- 批量 ----


def test_resolve_rows_batch(resolve_env):
    db = resolve_env["db"]
    rows = [
        _parsed(holder=""),                          # 新增部件
        _parsed(bmc_ip="192.0.2.99", holder=""),     # BMC IP 找不到 → error
    ]
    resolved = resolve_rows(db, rows)
    assert resolved[0].action is Action.NEW
    assert resolved[1].action is Action.ERROR
