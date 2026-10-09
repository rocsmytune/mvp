"""AI 助手 LLM 配置接口与加密/连通性测试。"""

import httpx
from fastapi.testclient import TestClient

from app.core.crypto import decrypt_secret
from app.core.db import SessionLocal
from app.main import app
from app.models.llm_config import AppSetting
from app.services import llm_config as service

PLAIN_KEY = "sk-test-secret"  # 长度 14，mask = "sk-t****cret"


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _mock_http(monkeypatch, responses):
    """用 MockTransport 替换 httpx.Client，按顺序返回给定响应。"""
    calls = {"i": 0}

    def handler(request):
        idx = min(calls["i"], len(responses) - 1)
        calls["i"] += 1
        return responses[idx]

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(**kw):
        return real_client(transport=transport, **kw)

    monkeypatch.setattr("app.services.llm_config.httpx.Client", factory)


# ---------- 全局配置 ----------


def test_global_get_requires_auth():
    with TestClient(app) as client:
        assert client.get("/api/llm-config/global").status_code == 401


def test_global_put_requires_system_admin(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")  # material_admin
        resp = client.put(
            "/api/llm-config/global", json={"model": "m"}, headers=admin_h
        )
        assert resp.status_code == 403

        sa_h = _auth(client, "910004", "sysadmin-pass")
        resp = client.put(
            "/api/llm-config/global",
            json={
                "base_url": "http://llm.local/v1",
                "model": "glm",
                "daily_token_quota": 12345,
            },
            headers=sa_h,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_url"] == "http://llm.local/v1"
    assert body["model"] == "glm"
    assert body["daily_token_quota"] == 12345
    assert body["configured"] is True


def test_global_default_quota_and_not_configured(crud_users):
    # 清空全局配置，验证 GET 惰性创建时回默认配额、未配置状态。
    db = SessionLocal()
    try:
        db.query(AppSetting).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        body = client.get("/api/llm-config/global", headers=h).json()
    assert body["daily_token_quota"] == 50000
    assert body["configured"] is False


def test_global_api_key_masked_and_encrypted(crud_users):
    with TestClient(app) as client:
        sa_h = _auth(client, "910004", "sysadmin-pass")
        resp = client.put(
            "/api/llm-config/global",
            json={"base_url": "http://llm.local/v1", "model": "m", "api_key": PLAIN_KEY},
            headers=sa_h,
        )
        assert resp.status_code == 200
        assert resp.json()["api_key_masked"] == "sk-t****cret"
        assert PLAIN_KEY not in resp.text

    db = SessionLocal()
    try:
        s = db.get(AppSetting, 1)
        assert s.llm_api_key_enc and s.llm_api_key_enc != PLAIN_KEY
        assert decrypt_secret(s.llm_api_key_enc) == PLAIN_KEY
    finally:
        db.close()


# ---------- 个人配置 ----------


def test_personal_config_own_only(crud_users):
    with TestClient(app) as client:
        member_h = _auth(client, "910003", "member-pass")
        resp = client.put(
            "/api/llm-config/me",
            json={"base_url": "http://p.local/v1", "model": "pm", "api_key": "sk-personal"},
            headers=member_h,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["base_url"] == "http://p.local/v1"
        assert body["model"] == "pm"
        assert body["enabled"] is True
        assert body["api_key_masked"] and "sk-personal" not in resp.text

        g = client.get("/api/llm-config/me", headers=member_h).json()
        assert g["model"] == "pm"

        # 其他用户读自己的配置为空，互不干扰
        admin_h = _auth(client, "910001", "admin-pass")
        empty = client.get("/api/llm-config/me", headers=admin_h).json()
        assert empty["base_url"] is None and empty["model"] is None


def test_personal_update_without_api_key_keeps_old(crud_users):
    with TestClient(app) as client:
        member_h = _auth(client, "910003", "member-pass")
        client.put(
            "/api/llm-config/me",
            json={"base_url": "http://p.local/v1", "model": "pm", "api_key": "sk-keep"},
            headers=member_h,
        )
        # 不传 api_key，只改 model，应保留原 key
        resp = client.put("/api/llm-config/me", json={"model": "pm2"}, headers=member_h)
        assert resp.status_code == 200
        assert resp.json()["model"] == "pm2"
        assert resp.json()["api_key_masked"] is not None

    db = SessionLocal()
    try:
        from app.models.llm_config import UserLlmConfig
        from app.models.user import User

        uid = db.query(User.id).filter(User.employee_no == "910003").scalar()
        cfg = (
            db.query(UserLlmConfig)
            .filter(UserLlmConfig.user_id == uid)
            .first()
        )
        assert cfg is not None
        assert decrypt_secret(cfg.llm_api_key_enc) == "sk-keep"
    finally:
        db.close()


# ---------- 连通性测试 ----------


def test_connection_endpoint_requires_auth():
    with TestClient(app) as client:
        resp = client.post("/api/llm-config/test", json={"base_url": "http://x"})
        assert resp.status_code == 401


def test_connection_endpoint(crud_users, monkeypatch):
    monkeypatch.setattr(service, "test_connection", lambda b, k, m: (True, "ok"))
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post(
            "/api/llm-config/test",
            json={"base_url": "http://x", "api_key": "k", "model": "m"},
            headers=h,
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "message": "ok"}


def test_connection_ok_via_models(monkeypatch):
    _mock_http(monkeypatch, [httpx.Response(200, json={"data": []})])
    ok, _ = service.test_connection("http://llm.local/v1", "sk", "m")
    assert ok is True


def test_connection_fallback_to_chat(monkeypatch):
    _mock_http(
        monkeypatch,
        [httpx.Response(404, json={}), httpx.Response(200, json={"choices": []})],
    )
    ok, _ = service.test_connection("http://llm.local/v1", "sk", "m")
    assert ok is True


def test_connection_failure(monkeypatch):
    _mock_http(
        monkeypatch,
        [httpx.Response(404, json={}), httpx.Response(500, json={})],
    )
    ok, msg = service.test_connection("http://llm.local/v1", "sk", "m")
    assert ok is False
    assert "500" in msg


def test_connection_network_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("boom")

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def factory(**kw):
        return real_client(transport=transport, **kw)

    monkeypatch.setattr("app.services.llm_config.httpx.Client", factory)
    ok, msg = service.test_connection("http://llm.local/v1", "sk", "m")
    assert ok is False
    assert "无法连接" in msg
