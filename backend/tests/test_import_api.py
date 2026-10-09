from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.import_batch import ImportBatch
from app.models.user import User


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _mk_server(client, h, cabinet_id, bmc_ip, sn=None, u_start=1, u_end=2):
    payload = {
        "type": "server",
        "cabinet_id": cabinet_id,
        "u_start": u_start,
        "u_end": u_end,
        "bmc_ip": bmc_ip,
        "sn": sn,
    }
    resp = client.post("/api/assets", json=payload, headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _row(**overrides):
    base = {
        "bmc_ip": "192.0.2.10",
        "machine_sn": None,
        "material_type": "硬盘",
        "sn": "DISK-1",
        "material_code": None,
        "material_name": None,
        "remark": None,
        "holder": None,
    }
    base.update(overrides)
    return base


def _upload(client, h, rows, file_name=None):
    resp = client.post(
        "/api/import/upload",
        json={"file_name": file_name, "rows": rows},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _confirm(client, h, batch_id):
    return client.post("/api/import/confirm", json={"batch_id": batch_id}, headers=h)


# ---------- 预览 + 新增部件 ----------


def test_upload_preview_new_component(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        up = _upload(client, h, [_row()], file_name="物料表.xlsx")
    assert up["summary"] == {
        "total": 1,
        "new": 1,
        "update": 0,
        "no_change": 0,
        "error": 0,
        "warning": 0,
    }
    row = up["rows"][0]
    assert row["action"] == "new"
    assert row["cabinet_name"] == "T-A01-02"
    assert row["asset_sn"] == "SRV-1"

    db = SessionLocal()
    try:
        batch = db.query(ImportBatch).filter(ImportBatch.id == up["batch_id"]).first()
        assert batch is not None
        assert batch.status == "previewed"
    finally:
        db.close()


def test_confirm_creates_component_and_changelog(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        up = _upload(client, h, [_row(material_name="SAS-960G")])
        resp = _confirm(client, h, up["batch_id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "committed"
    assert body["summary"] == {"total": 1, "created": 1, "updated": 0, "skipped": 0}
    assert body["rows"][0]["result"] == "created"

    db = SessionLocal()
    try:
        comp = (
            db.query(Component)
            .filter(Component.sn == "DISK-1", Component.deleted_at.is_(None))
            .first()
        )
        assert comp is not None
        assert comp.category == "硬盘"
        assert comp.name == "SAS-960G"
        assert comp.sn_source == "import"

        logs = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_id == comp.id, ChangeLog.target_type == "component")
            .all()
        )
        assert len(logs) == 1
        assert logs[0].action == "create"
        assert logs[0].source == "import"
        assert logs[0].batch_id == up["batch_id"]
    finally:
        db.close()


# ---------- 更新：字段级变动点 ----------


def test_confirm_updates_component_field_diff(crud_users):
    server_id = None
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        srv = _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        server_id = srv["id"]

    db = SessionLocal()
    try:
        comp = Component(asset_id=server_id, category="硬盘", sn="DISK-1", name="旧名称")
        db.add(comp)
        db.commit()
        db.refresh(comp)
        comp_id = comp.id
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(client, h, [_row(material_name="新名称")])
        resp = _confirm(client, h, up["batch_id"])
    assert resp.json()["summary"]["updated"] == 1

    db = SessionLocal()
    try:
        comp = db.query(Component).filter(Component.id == comp_id).first()
        assert comp.name == "新名称"
        upd = (
            db.query(ChangeLog)
            .filter(
                ChangeLog.target_id == comp_id,
                ChangeLog.field == "name",
                ChangeLog.action == "update",
            )
            .first()
        )
        assert upd is not None
        assert (upd.old_value, upd.new_value, upd.source) == ("旧名称", "新名称", "import")
        assert upd.batch_id == up["batch_id"]
    finally:
        db.close()


def test_confirm_move_cross_cabinet(crud_users):
    s2_id = None
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        s1 = _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        s2 = _mk_server(
            client, h, crud_users["cab_owner"].id, "192.0.2.20", sn="SRV-2", u_start=3, u_end=4
        )
        s2_id = s2["id"]

    db = SessionLocal()
    try:
        comp = Component(asset_id=s1["id"], category="硬盘", sn="DISK-1")
        db.add(comp)
        db.commit()
        db.refresh(comp)
        comp_id = comp.id
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(client, h, [_row(bmc_ip="192.0.2.20")])
        resp = _confirm(client, h, up["batch_id"])
    assert resp.json()["summary"]["updated"] == 1

    db = SessionLocal()
    try:
        comp = db.query(Component).filter(Component.id == comp_id).first()
        assert comp.asset_id == s2_id
        mov = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_id == comp_id, ChangeLog.field == "asset_id")
            .first()
        )
        assert mov is not None
        assert (mov.old_value, mov.new_value) == (str(s1["id"]), str(s2_id))
    finally:
        db.close()


# ---------- 定位失败 / 整机SN 不一致 ----------


def test_bmc_ip_not_found_is_error_and_skipped(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(client, h, [_row(bmc_ip="192.0.2.99")])
        assert up["summary"]["error"] == 1
        assert up["rows"][0]["action"] == "error"
        resp = _confirm(client, h, up["batch_id"])
    assert resp.json()["summary"]["skipped"] == 1
    assert "未找到" in resp.json()["rows"][0]["message"]


def test_machine_sn_mismatch_warns_but_commits(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-REAL")
        up = _upload(client, h, [_row(machine_sn="SRV-OTHER")])
        assert up["summary"]["warning"] == 1
        resp = _confirm(client, h, up["batch_id"])
    assert resp.json()["summary"]["created"] == 1


# ---------- 挂账人 ----------


def test_holder_matched(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10")
        up = _upload(client, h, [_row(holder="910002 测试柜主")])
        _confirm(client, h, up["batch_id"])

    db = SessionLocal()
    try:
        comp = (
            db.query(Component)
            .filter(Component.sn == "DISK-1", Component.deleted_at.is_(None))
            .first()
        )
        assert comp.holder_id == crud_users["owner"].id
        assert comp.holder_name == "测试柜主"
    finally:
        db.close()


def test_holder_unmatched(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10")
        up = _upload(client, h, [_row(holder="999999 张三")])
        assert up["rows"][0]["holder_name"] == "999999 张三"
        _confirm(client, h, up["batch_id"])

    db = SessionLocal()
    try:
        comp = (
            db.query(Component)
            .filter(Component.sn == "DISK-1", Component.deleted_at.is_(None))
            .first()
        )
        assert comp.holder_id is None
        assert comp.holder_name == "999999 张三"
    finally:
        db.close()


# ---------- 权限：三种角色 ----------


def test_member_cannot_import(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        up = _upload(client, admin_h, [_row()])
        member_h = _auth(client, "910003", "member-pass")
        resp = _confirm(client, member_h, up["batch_id"])
    assert resp.status_code == 403


def test_owner_can_import_own_cabinet(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        _mk_server(client, admin_h, crud_users["cab_owner"].id, "192.0.2.10")
        owner_h = _auth(client, "910002", "owner-pass")
        up = _upload(client, owner_h, [_row()])
        resp = _confirm(client, owner_h, up["batch_id"])
    assert resp.status_code == 200
    assert resp.json()["summary"]["created"] == 1


def test_owner_cannot_import_other_cabinet(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        _mk_server(client, admin_h, crud_users["cab_admin"].id, "192.0.2.10")
        owner_h = _auth(client, "910002", "owner-pass")
        up = _upload(client, owner_h, [_row()])
        resp = _confirm(client, owner_h, up["batch_id"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["skipped"] == 1
    assert body["rows"][0]["result"] == "skipped"
    assert "无权" in body["rows"][0]["message"]


# ---------- 服务器 sn：manual 保护 ----------


def test_server_sn_manual_not_overwritten(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="MANUAL-SN")

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(
            client, h, [_row(material_type="整机", sn="NEW-SN", machine_sn="NEW-SN")]
        )
        resp = _confirm(client, h, up["batch_id"])
    body = resp.json()
    assert body["summary"]["updated"] == 1
    assert "manual" in body["rows"][0]["message"]

    db = SessionLocal()
    try:
        asset = db.query(Asset).filter(Asset.bmc_ip == "192.0.2.10").first()
        assert asset.sn == "MANUAL-SN"
    finally:
        db.close()


def test_server_sn_import_applied_when_not_manual(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10")  # 无 sn

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(
            client,
            h,
            [_row(material_type="整机", sn="IMPORTED-SN", machine_sn="IMPORTED-SN")],
        )
        resp = _confirm(client, h, up["batch_id"])
    assert resp.json()["summary"]["updated"] == 1

    db = SessionLocal()
    try:
        asset = db.query(Asset).filter(Asset.bmc_ip == "192.0.2.10").first()
        assert asset.sn == "IMPORTED-SN"
        assert asset.field_source.get("sn") == "import"
    finally:
        db.close()


# ---------- 批次状态机 / 列表 ----------


def test_confirm_twice_conflict(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10")
        up = _upload(client, h, [_row()])
        r1 = _confirm(client, h, up["batch_id"])
        assert r1.status_code == 200
        r2 = _confirm(client, h, up["batch_id"])
        assert r2.status_code == 409


def test_list_batches(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _upload(client, h, [_row()])
        resp = client.get("/api/import/batches", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    assert body["items"][0]["status"] == "previewed"


# ---------- E2：同批重复 / 无变化 ----------


def test_duplicate_same_batch_second_row_skipped(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        up = _upload(client, h, [_row(), _row()], file_name="dup.xlsx")

    assert up["summary"]["new"] == 1
    assert up["summary"]["error"] == 1
    assert [r["action"] for r in up["rows"]] == ["new", "error"]
    assert "同批内" in up["rows"][1]["issues"][0]["message"]

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = _confirm(client, h, up["batch_id"])
    body = resp.json()
    assert body["summary"] == {"total": 2, "created": 1, "updated": 0, "skipped": 1}

    # 只有首行入库，且不撞唯一索引（仅一条 DISK-1）
    db = SessionLocal()
    try:
        n = (
            db.query(Component)
            .filter(Component.sn == "DISK-1", Component.deleted_at.is_(None))
            .count()
        )
        assert n == 1
    finally:
        db.close()


def test_no_change_skipped_on_confirm(crud_users):
    server_id = None
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        srv = _mk_server(client, h, crud_users["cab_admin"].id, "192.0.2.10", sn="SRV-1")
        server_id = srv["id"]

    db = SessionLocal()
    try:
        comp = Component(asset_id=server_id, category="硬盘", sn="DISK-1", name="SAS-960G")
        db.add(comp)
        db.commit()
        db.refresh(comp)
        comp_id = comp.id
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        up = _upload(client, h, [_row(material_name="SAS-960G")])
        assert up["summary"]["no_change"] == 1
        assert up["summary"]["update"] == 0
        assert up["rows"][0]["action"] == "no_change"
        resp = _confirm(client, h, up["batch_id"])
    body = resp.json()
    assert body["summary"]["updated"] == 0
    assert body["summary"]["skipped"] == 1
    assert body["rows"][0]["result"] == "skipped"
    assert "无变化" in body["rows"][0]["message"]

    db = SessionLocal()
    try:
        # 未产生 update 日志
        upd = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_id == comp_id, ChangeLog.action == "update")
            .count()
        )
        assert upd == 0
    finally:
        db.close()
