from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.component import Component


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(crud_users):
    """在测试机柜下构造服务器/交换机/两个部件，字段覆盖导出需要映射的键。"""
    db = SessionLocal()
    try:
        srv = Asset(
            type="server",
            cabinet_id=crud_users["cab_admin"].id,
            u_start=1,
            u_end=2,
            sn="T-EXP-SRV",
            bmc_ip="192.0.2.110",
            asset_tag="T-EXP-TAG",
            model="DL380",
            cpu_model="Xeon",
            ip_inband="10.0.0.110",
            status="in_use",
            remark="服务器备注",
        )
        sw = Asset(
            type="switch",
            cabinet_id=crud_users["cab_owner"].id,
            u_start=3,
            u_end=4,
            sn="T-EXP-SW",
            bmc_ip="192.0.2.120",
            holder_id=crud_users["owner"].id,
            holder_name="测试柜主",
        )
        db.add_all([srv, sw])
        db.flush()
        c1 = Component(
            asset_id=srv.id,
            category="硬盘",
            sn="T-EXP-DISK",
            name="SAS-960G",
            material_code="MAT-1",
            holder_id=crud_users["owner"].id,
            holder_name="测试柜主",
            remark="部件备注",
        )
        c2 = Component(
            asset_id=srv.id,
            category="内存",
            sn="T-EXP-MEM",
            name=None,
            holder_id=None,
            holder_name="999999 张三",
        )
        db.add_all([c1, c2])
        db.commit()
    finally:
        db.close()


def test_export_snapshot_admin_ok(crud_users):
    _seed(crud_users)
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.get("/api/export/snapshot", headers=h)
    assert resp.status_code == 200
    body = resp.json()

    # 机柜：含机房编码与柜主工号（业务键）
    cab_admin = next(c for c in body["cabinets"] if c["name"] == "T-A01-02")
    assert cab_admin["room_code"] == "T-ROOM-1"
    assert cab_admin["owner_employee_no"] == "910001"
    assert cab_admin["total_u"] == 45
    cab_owner = next(c for c in body["cabinets"] if c["name"] == "T-A01-01")
    assert cab_owner["owner_employee_no"] == "910002"

    # 资产：服务器→整机、交换机→交换机；U 位与关键字段、挂账人工号
    srv = next(a for a in body["assets"] if a["sn"] == "T-EXP-SRV")
    assert srv["type"] == "整机"
    assert srv["cabinet_name"] == "T-A01-02"
    assert srv["room_code"] == "T-ROOM-1"
    assert srv["u_start"] == 1 and srv["u_end"] == 2
    assert srv["model"] == "DL380"
    assert srv["cpu_model"] == "Xeon"
    assert srv["ip_inband"] == "10.0.0.110"
    assert srv["asset_tag"] == "T-EXP-TAG"
    assert srv["remark"] == "服务器备注"
    sw = next(a for a in body["assets"] if a["sn"] == "T-EXP-SW")
    assert sw["type"] == "交换机"
    assert sw["cabinet_name"] == "T-A01-01"
    assert sw["holder_employee_no"] == "910002"
    assert sw["holder_name"] == "测试柜主"

    # 部件：8 列对齐（bmc_ip / 整机SN / 物料类型 / SN / 物料编码 / 物料名称 / 备注 / 挂账人）
    disk = next(c for c in body["components"] if c["sn"] == "T-EXP-DISK")
    assert disk["bmc_ip"] == "192.0.2.110"
    assert disk["machine_sn"] == "T-EXP-SRV"
    assert disk["material_type"] == "硬盘"
    assert disk["material_code"] == "MAT-1"
    assert disk["material_name"] == "SAS-960G"
    assert disk["remark"] == "部件备注"
    assert disk["holder"] == "910002 测试柜主"  # 匹配：合成「工号 姓名」
    mem = next(c for c in body["components"] if c["sn"] == "T-EXP-MEM")
    assert mem["holder"] == "999999 张三"  # 未匹配：保留原文


def test_export_owner_forbidden(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910002", "owner-pass")
        resp = client.get("/api/export/snapshot", headers=h)
    assert resp.status_code == 403


def test_export_member_forbidden(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.get("/api/export/snapshot", headers=h)
    assert resp.status_code == 403


def test_export_excludes_soft_deleted(crud_users):
    db = SessionLocal()
    try:
        del_asset = Asset(
            type="server",
            cabinet_id=crud_users["cab_admin"].id,
            u_start=5,
            u_end=5,
            sn="T-EXP-DEL",
            bmc_ip="192.0.2.130",
            deleted_at=datetime.now(timezone.utc),
        )
        db.add(del_asset)
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.get("/api/export/snapshot", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert all(a["sn"] != "T-EXP-DEL" for a in body["assets"])
