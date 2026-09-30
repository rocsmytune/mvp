from fastapi.testclient import TestClient

from app.main import app


def test_health():
    """骨架冒烟测试：验证后端能启动且能连上数据库。"""
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
