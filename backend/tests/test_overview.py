from fastapi.testclient import TestClient

from app.main import app


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_overview_counts_and_cabinet_stats(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        before = client.get("/api/overview", headers=h).json()

        cab = crud_users["cab_admin"]
        # 2 台设备：1U + 2U
        assert (
            client.post(
                "/api/assets",
                json={"type": "server", "cabinet_id": cab.id, "u_start": 1, "u_end": 1},
                headers=h,
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/assets",
                json={"type": "server", "cabinet_id": cab.id, "u_start": 2, "u_end": 3},
                headers=h,
            ).status_code
            == 201
        )
        # 1 台待整理池设备（sn 带测试标记，供清理）
        assert (
            client.post(
                "/api/assets", json={"type": "server", "sn": "T-POOL-1"}, headers=h
            ).status_code
            == 201
        )

        after = client.get("/api/overview", headers=h).json()

    assert after["pool_count"] == before["pool_count"] + 1
    entry = next(c for c in after["cabinets"] if c["id"] == cab.id)
    assert entry["device_count"] == 2
    assert entry["used_u"] == 3
    assert entry["room_code"] == "T-ROOM-1"
