from fastapi.testclient import TestClient

from app.main import app


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_asset_changelog_flow(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        created = client.post(
            "/api/assets",
            json={
                "type": "server",
                "cabinet_id": crud_users["cab_admin"].id,
                "u_start": 7,
                "u_end": 7,
                "sn": "LOG-SN-1",
            },
            headers=h,
        )
        assert created.status_code == 201
        aid = created.json()["id"]
        client.patch(f"/api/assets/{aid}", json={"sn": "LOG-SN-2"}, headers=h)

        resp = client.get(f"/api/assets/{aid}/changelogs", headers=h)
        assert resp.status_code == 200
        logs = resp.json()
        # 时间倒序：update 在前，create 在后
        assert [l["action"] for l in logs] == ["update", "create"]
        upd = logs[0]
        assert (upd["field"], upd["old_value"], upd["new_value"]) == ("sn", "LOG-SN-1", "LOG-SN-2")
        assert upd["operator_name"] == "测试管理员"
        assert logs[1]["action"] == "create"
        assert logs[1]["operator_name"] == "测试管理员"


def test_member_can_view_changelog(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        created = client.post(
            "/api/assets",
            json={
                "type": "server",
                "cabinet_id": crud_users["cab_admin"].id,
                "u_start": 8,
                "u_end": 8,
                "sn": "LOG-M-1",
            },
            headers=admin_h,
        ).json()
        member_h = _auth(client, "910003", "member-pass")
        resp = client.get(f"/api/assets/{created['id']}/changelogs", headers=member_h)
        assert resp.status_code == 200
        assert len(resp.json()) == 1


def test_changelog_missing_asset_404(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.get("/api/assets/999999999/changelogs", headers=h)
        assert resp.status_code == 404
