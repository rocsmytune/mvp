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


def _create_room(client, h, code, **extra):
    payload = {"code": code}
    payload.update(extra)
    resp = client.post("/api/rooms", json=payload, headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_cab(client, h, room_id, name, **extra):
    payload = {"room_id": room_id, "name": name}
    payload.update(extra)
    return client.post("/api/cabinets", json=payload, headers=h)


# ---------- 权限：写操作仅 admin ----------


def test_admin_can_create_room_and_cabinet(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-1", city="测试市", zone="绿区")
        resp = _create_cab(client, h, room["id"], "T-CAB-1")
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "T-CAB-1"
        assert body["owner_id"] is None
        assert body["room_code"] == "T-RM-1"


def test_non_admin_cannot_create_room(crud_users):
    with TestClient(app) as client:
        owner_h = _auth(client, "910002", "owner-pass")
        member_h = _auth(client, "910003", "member-pass")
        assert client.post("/api/rooms", json={"code": "T-RM-X1"}, headers=owner_h).status_code == 403
        assert client.post("/api/rooms", json={"code": "T-RM-X2"}, headers=member_h).status_code == 403


def test_non_admin_cannot_create_cabinet(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, admin_h, "T-RM-2")
        owner_h = _auth(client, "910002", "owner-pass")
        member_h = _auth(client, "910003", "member-pass")
        assert client.post("/api/cabinets", json={"room_id": room["id"], "name": "T-CAB-X1"}, headers=owner_h).status_code == 403
        assert client.post("/api/cabinets", json={"room_id": room["id"], "name": "T-CAB-X2"}, headers=member_h).status_code == 403


def test_non_admin_cannot_assign_owner(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, admin_h, "T-RM-3")
        cab = _create_cab(client, admin_h, room["id"], "T-CAB-2").json()
        owner_h = _auth(client, "910002", "owner-pass")
        resp = client.post(
            "/api/cabinets/assign-owner",
            json={"cabinet_ids": [cab["id"]], "owner_id": crud_users["owner"].id},
            headers=owner_h,
        )
        assert resp.status_code == 403


# ---------- 唯一性 ----------


def test_room_code_unique(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _create_room(client, h, "T-RM-4")
        resp = client.post("/api/rooms", json={"code": "T-RM-4"}, headers=h)
        assert resp.status_code == 409


def test_cabinet_name_unique_within_room(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-5")
        assert _create_cab(client, h, room["id"], "T-CAB-3").status_code == 201
        resp = _create_cab(client, h, room["id"], "T-CAB-3")
        assert resp.status_code == 409


# ---------- 指派柜主校验 ----------


def test_assign_owner_requires_cabinet_owner_role(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-6")
        cab = _create_cab(client, h, room["id"], "T-CAB-4").json()
        # member 角色不能当柜主
        resp = client.patch(
            f"/api/cabinets/{cab['id']}",
            json={"owner_id": crud_users["member"].id},
            headers=h,
        )
        assert resp.status_code == 422
        # 合法柜主
        resp = client.patch(
            f"/api/cabinets/{cab['id']}",
            json={"owner_id": crud_users["owner"].id},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["owner_id"] == crud_users["owner"].id
        assert resp.json()["owner_name"] == "测试柜主"


# ---------- 删除保护 ----------


def test_delete_cabinet_with_assets_blocked(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-7")
        cab = _create_cab(client, h, room["id"], "T-CAB-5").json()
        client.post(
            "/api/assets",
            json={"type": "server", "cabinet_id": cab["id"], "u_start": 1, "u_end": 1},
            headers=h,
        )
        resp = client.delete(f"/api/cabinets/{cab['id']}", headers=h)
        assert resp.status_code == 409


def test_delete_room_with_cabinets_blocked(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-8")
        _create_cab(client, h, room["id"], "T-CAB-6")
        resp = client.delete(f"/api/rooms/{room['id']}", headers=h)
        assert resp.status_code == 409


# ---------- ChangeLog ----------


def test_changelog_on_room_and_cabinet_writes(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-9")
        cab = _create_cab(client, h, room["id"], "T-CAB-7").json()
        client.patch(f"/api/cabinets/{cab['id']}", json={"owner_id": crud_users["owner"].id}, headers=h)
        client.delete(f"/api/cabinets/{cab['id']}", headers=h)

    db = SessionLocal()
    try:
        room_logs = db.query(ChangeLog).filter(
            ChangeLog.target_type == "room", ChangeLog.target_id == room["id"]
        ).all()
        assert [l.action for l in room_logs] == ["create"]
        cab_logs = db.query(ChangeLog).filter(
            ChangeLog.target_type == "cabinet", ChangeLog.target_id == cab["id"]
        ).all()
        assert sorted(l.action for l in cab_logs) == ["create", "delete", "update"]
    finally:
        db.close()


# ---------- 批量指派 ----------


def test_batch_assign_owner(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, h, "T-RM-10")
        c1 = _create_cab(client, h, room["id"], "T-CAB-8").json()
        c2 = _create_cab(client, h, room["id"], "T-CAB-9").json()
        resp = client.post(
            "/api/cabinets/assign-owner",
            json={"cabinet_ids": [c1["id"], c2["id"]], "owner_id": crud_users["owner"].id},
            headers=h,
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 2
        # 校验生效
        listing = client.get(f"/api/cabinets?room_id={room['id']}", headers=h).json()
        owners = {i["id"]: i["owner_id"] for i in listing["items"]}
        assert owners[c1["id"]] == crud_users["owner"].id
        assert owners[c2["id"]] == crud_users["owner"].id


# ---------- 读权限（所有角色可看） ----------


def test_member_can_read_rooms_and_cabinets(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        room = _create_room(client, admin_h, "T-RM-11")
        _create_cab(client, admin_h, room["id"], "T-CAB-10")
        member_h = _auth(client, "910003", "member-pass")
        assert client.get("/api/rooms", headers=member_h).status_code == 200
        assert client.get("/api/cabinets", headers=member_h).status_code == 200
