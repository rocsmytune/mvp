"""用户管理：仅系统管理员，含权限、唯一工号、禁用、自我保护与 ChangeLog。"""
import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.change_log import ChangeLog
from app.models.user import User


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# 测试内新建的用户（工号 9200 段）在用例间清理，避免污染列表断言。
@pytest.fixture(autouse=True)
def _cleanup_created_users():
    yield
    db = SessionLocal()
    try:
        db.query(User).filter(User.employee_no.like("9200%")).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


# ---------- 权限：非系统管理员一律 403 ----------


def test_material_admin_cannot_list_users(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.get("/api/users", headers=h)
    assert resp.status_code == 403


def test_material_admin_cannot_create_user(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.post(
            "/api/users",
            json={"employee_no": "920001", "name": "x", "role": "member", "password": "p123"},
            headers=h,
        )
    assert resp.status_code == 403


def test_owner_cannot_list_users(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910002", "owner-pass")
        resp = client.get("/api/users", headers=h)
    assert resp.status_code == 403


def test_member_cannot_list_users(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.get("/api/users", headers=h)
    assert resp.status_code == 403


# ---------- 系统管理员 CRUD ----------


def test_system_admin_list_users(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        resp = client.get("/api/users", headers=h)
    assert resp.status_code == 200
    emps = {u["employee_no"] for u in resp.json()["items"]}
    assert {"910001", "910002", "910003", "910004"} <= emps


def test_system_admin_create_and_duplicate(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        resp = client.post(
            "/api/users",
            json={"employee_no": "920001", "name": "新用户", "role": "member", "password": "pass1234"},
            headers=h,
        )
    assert resp.status_code == 201
    assert resp.json()["role"] == "member"

    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        resp2 = client.post(
            "/api/users",
            json={"employee_no": "920001", "name": "x", "role": "member", "password": "p123"},
            headers=h,
        )
    assert resp2.status_code == 409


def test_system_admin_update_user(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        lst = client.get("/api/users", headers=h).json()["items"]
        member = next(u for u in lst if u["employee_no"] == "910003")
        resp = client.patch(
            f"/api/users/{member['id']}",
            json={"name": "成员乙改名", "role": "cabinet_owner", "password": "newpass123"},
            headers=h,
        )
    assert resp.status_code == 200
    assert resp.json()["name"] == "成员乙改名"
    assert resp.json()["role"] == "cabinet_owner"


def test_disable_user_blocks_login(crud_users):
    with TestClient(app) as client:
        member_token = _auth(client, "910003", "member-pass")["Authorization"]
        sys_h = _auth(client, "910004", "sysadmin-pass")
        lst = client.get("/api/users", headers=sys_h).json()["items"]
        member = next(u for u in lst if u["employee_no"] == "910003")
        resp = client.patch(
            f"/api/users/{member['id']}", json={"active": False}, headers=sys_h
        )
    assert resp.status_code == 200
    assert resp.json()["active"] is False

    # 已停用：现有 token 与重新登录均应失效。
    with TestClient(app) as client:
        me = client.get("/api/auth/me", headers={"Authorization": member_token})
    assert me.status_code == 401
    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"employee_no": "910003", "password": "member-pass"},
        )
    assert login.status_code == 401


# ---------- 自我保护 ----------


def test_cannot_disable_self(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        lst = client.get("/api/users", headers=h).json()["items"]
        me = next(u for u in lst if u["employee_no"] == "910004")
        resp = client.patch(f"/api/users/{me['id']}", json={"active": False}, headers=h)
    assert resp.status_code == 403


def test_cannot_demote_self(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        lst = client.get("/api/users", headers=h).json()["items"]
        me = next(u for u in lst if u["employee_no"] == "910004")
        resp = client.patch(f"/api/users/{me['id']}", json={"role": "member"}, headers=h)
    assert resp.status_code == 403


# ---------- 机柜指派柜主下拉（cabinet-owners） ----------


def test_cabinet_owners_admins_see_only_owner_role(crud_users):
    for emp, pw in [("910001", "admin-pass"), ("910004", "sysadmin-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = client.get("/api/users/cabinet-owners", headers=h)
        assert resp.status_code == 200
        emps = {u["employee_no"] for u in resp.json()}
        # 只返回 cabinet_owner（910002），不含管理员/成员/系统管理员。
        assert emps == {"910002"}


def test_cabinet_owners_forbidden_for_owner_and_member(crud_users):
    for emp, pw in [("910002", "owner-pass"), ("910003", "member-pass")]:
        with TestClient(app) as client:
            h = _auth(client, emp, pw)
            resp = client.get("/api/users/cabinet-owners", headers=h)
        assert resp.status_code == 403


# ---------- ChangeLog ----------


def test_changelog_on_user_create_update(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910004", "sysadmin-pass")
        created = client.post(
            "/api/users",
            json={"employee_no": "920002", "name": "日志用户", "role": "member", "password": "pass1234"},
            headers=h,
        ).json()
        uid = created["id"]
        client.patch(f"/api/users/{uid}", json={"name": "日志用户改"}, headers=h)

    db = SessionLocal()
    try:
        logs = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_type == "user", ChangeLog.target_id == uid)
            .all()
        )
        actions = sorted(l.action for l in logs)
        assert actions == ["create", "update"]
        upd = next(l for l in logs if l.action == "update")
        assert (upd.field, upd.new_value) == ("name", "日志用户改")
    finally:
        db.close()
