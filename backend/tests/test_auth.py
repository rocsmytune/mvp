from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "test-password-123"  # 与 conftest 中测试用户密码一致


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
