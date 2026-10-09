from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.change_log import ChangeLog
from app.models.user import User

PASSWORD = "test-password-123"  # 与 conftest 中测试用户密码一致


def _delete_registered(*employee_nos):
    """清理自助注册产生的用户及其 ChangeLog（operator/target 均指向本人）。"""
    db = SessionLocal()
    try:
        ids = [
            r[0]
            for r in db.query(User.id)
            .filter(User.employee_no.in_(employee_nos))
            .all()
        ]
        if ids:
            db.query(ChangeLog).filter(ChangeLog.operator_id.in_(ids)).delete(
                synchronize_session=False
            )
            db.query(ChangeLog).filter(
                ChangeLog.target_type == "user", ChangeLog.target_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


def test_login_success(test_user):
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/login",
            json={"employee_no": test_user.employee_no, "password": PASSWORD},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["employee_no"] == test_user.employee_no
    assert body["user"]["role"] == "material_admin"


def test_login_wrong_password(test_user):
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/login",
            json={"employee_no": test_user.employee_no, "password": "wrong"},
        )
    assert resp.status_code == 401


def test_login_unknown_user():
    with TestClient(app) as client:
        resp = client.post(
            "/api/auth/login",
            json={"employee_no": "999999", "password": "whatever"},
        )
    assert resp.status_code == 401


def test_me_with_valid_token(test_user):
    with TestClient(app) as client:
        token = client.post(
            "/api/auth/login",
            json={"employee_no": test_user.employee_no, "password": PASSWORD},
        ).json()["access_token"]
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["employee_no"] == test_user.employee_no


def test_me_without_token():
    with TestClient(app) as client:
        resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token():
    with TestClient(app) as client:
        resp = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
    assert resp.status_code == 401


# ---------- D4：自助注册 ----------


def test_register_member_then_login():
    emp = "900101"
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/auth/register",
                json={
                    "employee_no": emp,
                    "name": "注册成员",
                    "password": "reg-pass-123",
                    "role": "member",
                },
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["employee_no"] == emp
        assert body["name"] == "注册成员"
        assert body["role"] == "member"

        # 注册后可正常登录。
        with TestClient(app) as client:
            login = client.post(
                "/api/auth/login",
                json={"employee_no": emp, "password": "reg-pass-123"},
            )
        assert login.status_code == 200
        assert login.json()["user"]["role"] == "member"
    finally:
        _delete_registered(emp)


def test_register_cabinet_owner():
    emp = "900102"
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/auth/register",
                json={
                    "employee_no": emp,
                    "name": "注册柜主",
                    "password": "reg-pass-123",
                    "role": "cabinet_owner",
                },
            )
        assert resp.status_code == 201
        assert resp.json()["role"] == "cabinet_owner"
    finally:
        _delete_registered(emp)


def test_register_duplicate_employee_no():
    emp = "900103"
    try:
        with TestClient(app) as client:
            r1 = client.post(
                "/api/auth/register",
                json={
                    "employee_no": emp,
                    "name": "注册成员",
                    "password": "reg-pass-123",
                    "role": "member",
                },
            )
            assert r1.status_code == 201
            r2 = client.post(
                "/api/auth/register",
                json={
                    "employee_no": emp,
                    "name": "重复工号",
                    "password": "reg-pass-123",
                    "role": "member",
                },
            )
        assert r2.status_code == 409
    finally:
        _delete_registered(emp)


def test_register_rejects_admin_roles():
    for role in ("system_admin", "material_admin"):
        with TestClient(app) as client:
            resp = client.post(
                "/api/auth/register",
                json={
                    "employee_no": "900199",
                    "name": "越权注册",
                    "password": "reg-pass-123",
                    "role": role,
                },
            )
        assert resp.status_code == 422
