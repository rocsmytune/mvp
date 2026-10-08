"""字典管理：仅系统管理员可写，禁止删除，提供使用位置与 ChangeLog。"""
import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.dictionary import Dictionary


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# 本文件是唯一写字典的测试，用完清空整表，避免用例间泄漏（不污染其它测试）。
@pytest.fixture(autouse=True)
def _cleanup_dictionaries():
    yield
    db = SessionLocal()
    try:
        db.query(Dictionary).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create(client, h, kind, code, label):
    return client.post(
        "/api/dictionaries", json={"kind": kind, "code": code, "label": label}, headers=h
    )


# ---------- 权限：写仅系统管理员 ----------


def test_non_system_admin_cannot_create(crud_users):
    for emp, pw in [("910001", "admin-pass"), ("910002", "owner-pass"), ("910003", "member-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = _create(client, h, "asset_status", "in_use", "在用")
        assert resp.status_code == 403


def test_non_system_admin_cannot_update(crud_users):
    with TestClient(app) as client:
        sys_h = _auth(client, "910004", "sysadmin-pass")
        d = _create(client, sys_h, "asset_status", "in_use", "在用").json()
    for emp, pw in [("910001", "admin-pass"), ("910002", "owner-pass"), ("910003", "member-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = client.patch(
                f"/api/dictionaries/{d['id']}", json={"label": "改"}, headers=h
            )
        assert resp.status_code == 403


def test_read_open_to_all_roles(crud_users):
    with TestClient(app) as client:
        sys_h = _auth(client, "910004", "sysadmin-pass")
        _create(client, sys_h, "component_category", "硬盘", "硬盘")
    for emp, pw in [("910001", "admin-pass"), ("910002", "owner-pass"), ("910003", "member-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = client.get("/api/dictionaries", headers=h)
        assert resp.status_code == 200


# ---------- 系统管理员 CRUD ----------


def test_system_admin_create(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        resp = _create(client, h, "asset_status", "in_use", "在用")
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "asset_status"
    assert body["code"] == "in_use"
    assert body["label"] == "在用"


def test_duplicate_kind_code_conflict(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        r1 = _create(client, h, "asset_status", "in_use", "在用")
        r2 = _create(client, h, "asset_status", "in_use", "重复")
    assert r1.status_code == 201
    assert r2.status_code == 409


def test_update_dictionary(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        d = _create(client, h, "asset_status", "in_use", "在用").json()
        resp = client.patch(
            f"/api/dictionaries/{d['id']}", json={"label": "使用中", "sort_no": 5}, headers=h
        )
    assert resp.status_code == 200
    assert resp.json()["label"] == "使用中"
    assert resp.json()["sort_no"] == 5


def test_update_code_conflict(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        a = _create(client, h, "component_category", "硬盘", "硬盘").json()
        _create(client, h, "component_category", "内存", "内存")
        resp = client.patch(
            f"/api/dictionaries/{a['id']}", json={"code": "内存"}, headers=h
        )
    assert resp.status_code == 409


def test_non_system_admin_cannot_delete(crud_users):
    with TestClient(app) as client:
        sys_h = _auth(client, "910004", "sysadmin-pass")
        d = _create(client, sys_h, "asset_status", "in_use", "在用").json()
    for emp, pw in [("910001", "admin-pass"), ("910002", "owner-pass"), ("910003", "member-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = client.delete(f"/api/dictionaries/{d['id']}", headers=h)
        assert resp.status_code == 403


# ---------- 删除：未使用可删，被引用禁止 ----------


def test_delete_unused_allowed(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        d = _create(client, h, "asset_status", "in_use", "在用").json()
        resp = client.delete(f"/api/dictionaries/{d['id']}", headers=h)
        assert resp.status_code == 204
        lst = client.get("/api/dictionaries", headers=h).json()["items"]
        assert all(x["id"] != d["id"] for x in lst)


def test_delete_used_blocked(crud_users):
    # 造 1 台资产（status=in_use），使该字典值被引用。
    db = SessionLocal()
    try:
        db.add(
            Asset(
                type="server",
                cabinet_id=crud_users["cab_owner"].id,
                u_start=5,
                u_end=5,
                sn="T-USAGE-DEL",
                status="in_use",
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        d = _create(client, h, "asset_status", "in_use", "在用").json()
        resp = client.delete(f"/api/dictionaries/{d['id']}", headers=h)
    assert resp.status_code == 409


# ---------- 使用位置 ----------


def test_usage_reports_locations(crud_users):
    # 直接在库里造 1 台资产 + 1 个部件，归属 crud 机柜，由 crud_users teardown 清理。
    db = SessionLocal()
    try:
        asset = Asset(
            type="server",
            cabinet_id=crud_users["cab_owner"].id,
            u_start=10,
            u_end=11,
            sn="T-USAGE-SRV",
            model="测试服务器",
            status="in_use",
        )
        db.add(asset)
        db.flush()
        db.add(Component(asset_id=asset.id, category="硬盘", sn="T-USAGE-DISK", model="SSD-1T"))
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        s = _create(client, h, "asset_status", "in_use", "在用").json()
        c = _create(client, h, "component_category", "硬盘", "硬盘").json()

        lst = client.get("/api/dictionaries", headers=h).json()["items"]
        by_id = {d["id"]: d for d in lst}
        assert by_id[s["id"]]["usage_count"] == 1
        assert by_id[c["id"]]["usage_count"] == 1

        su = client.get(f"/api/dictionaries/{s['id']}/usage", headers=h).json()
        assert len(su) == 1
        assert su[0]["target_type"] == "asset"
        assert su[0]["sn"] == "T-USAGE-SRV"
        assert su[0]["cabinet_name"] == "T-A01-01"
        assert su[0]["u_start"] == 10

        cu = client.get(f"/api/dictionaries/{c['id']}/usage", headers=h).json()
        assert len(cu) == 1
        assert cu[0]["target_type"] == "component"
        assert cu[0]["sn"] == "T-USAGE-DISK"
        assert cu[0]["asset_sn"] == "T-USAGE-SRV"
        assert cu[0]["cabinet_name"] == "T-A01-01"


# ---------- ChangeLog ----------


def test_changelog_on_create_update(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        created = _create(client, h, "asset_status", "in_use", "在用").json()
        did = created["id"]
        client.patch(f"/api/dictionaries/{did}", json={"label": "使用中"}, headers=h)

    db = SessionLocal()
    try:
        logs = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_type == "dictionary", ChangeLog.target_id == did)
            .all()
        )
        actions = sorted(l.action for l in logs)
        assert actions == ["create", "update"]
        upd = next(l for l in logs if l.action == "update")
        assert (upd.field, upd.new_value) == ("label", "使用中")
    finally:
        db.close()
