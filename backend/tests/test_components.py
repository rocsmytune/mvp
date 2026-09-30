from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.change_log import ChangeLog


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_asset(client, h, cabinet_id, u_start, u_end):
    resp = client.post(
        "/api/assets",
        json={
            "type": "server",
            "cabinet_id": cabinet_id,
            "u_start": u_start,
            "u_end": u_end,
        },
        headers=h,
    )
    assert resp.status_code == 201
    return resp.json()


def test_admin_can_create_component_and_changelog(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _create_asset(client, h, crud_users["cab_admin"].id, 30, 30)
        resp = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "CPU", "sn": "CPU-SN-1"},
            headers=h,
        )
        assert resp.status_code == 201
        comp_id = resp.json()["id"]
        client.patch(f"/api/components/{comp_id}", json={"model": "Xeon-9999"}, headers=h)
        client.delete(f"/api/components/{comp_id}", headers=h)

    db = SessionLocal()
    try:
        logs = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_type == "component", ChangeLog.target_id == comp_id)
            .all()
        )
        assert sorted(l.action for l in logs) == ["create", "delete", "update"]
        upd = next(l for l in logs if l.action == "update")
        assert (upd.field, upd.new_value) == ("model", "Xeon-9999")
    finally:
        db.close()


def test_owner_cannot_add_component_to_other_cabinet_asset(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        asset = _create_asset(client, admin_h, crud_users["cab_admin"].id, 31, 31)
        owner_h = _auth(client, "910002", "owner-pass")
        resp = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "内存"},
            headers=owner_h,
        )
    assert resp.status_code == 403
