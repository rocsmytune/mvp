from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.change_log import ChangeLog
from app.models.user import User
from app.schemas.asset import AssetUpdate
from app.services import asset as asset_service


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_payload(cabinet_id, u_start, u_end, **extra):
    payload = {
        "type": "server",
        "cabinet_id": cabinet_id,
        "u_start": u_start,
        "u_end": u_end,
    }
    payload.update(extra)
    return payload


# ---------- 权限：三种角色 ----------


def test_admin_can_create_asset(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 1, 2, sn="SN-A-001"),
            headers=h,
        )
    assert resp.status_code == 201
    assert resp.json()["sn"] == "SN-A-001"


def test_owner_can_create_in_own_cabinet(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910002", "owner-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_owner"].id, 3, 3, sn="SN-B-001"),
            headers=h,
        )
    assert resp.status_code == 201


def test_owner_cannot_create_in_other_cabinet(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910002", "owner-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 1, 1),
            headers=h,
        )
    assert resp.status_code == 403


def test_member_cannot_create(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 1, 1),
            headers=h,
        )
    assert resp.status_code == 403


def test_member_cannot_delete(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        created = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 5, 5, sn="SN-DEL-1"),
            headers=admin_h,
        ).json()
        member_h = _auth(client, "910003", "member-pass")
        resp = client.delete(f"/api/assets/{created['id']}", headers=member_h)
    assert resp.status_code == 403


# ---------- U 位校验 ----------


def test_u_overlap_rejected(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        r1 = client.post(
            "/api/assets", json=_create_payload(cid, 10, 12), headers=h
        )
        assert r1.status_code == 201
        r2 = client.post(
            "/api/assets", json=_create_payload(cid, 12, 14), headers=h
        )
        assert r2.status_code == 409


def test_u_out_of_range_rejected(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 0, 2),
            headers=h,
        )
    assert resp.status_code == 422


def test_u_reversed_rejected(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.post(
            "/api/assets",
            json=_create_payload(crud_users["cab_admin"].id, 22, 21),
            headers=h,
        )
    assert resp.status_code == 422


def test_cabinet_asset_requires_u(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        resp = client.post(
            "/api/assets",
            json={"type": "server", "cabinet_id": crud_users["cab_admin"].id},
            headers=h,
        )
    assert resp.status_code == 422


# ---------- ChangeLog ----------


def test_changelog_on_create_update_delete(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        created = client.post(
            "/api/assets",
            json=_create_payload(cid, 20, 20, sn="OLD-SN"),
            headers=h,
        ).json()
        aid = created["id"]
        client.patch(f"/api/assets/{aid}", json={"sn": "NEW-SN"}, headers=h)
        client.delete(f"/api/assets/{aid}", headers=h)

    db = SessionLocal()
    try:
        logs = (
            db.query(ChangeLog)
            .filter(ChangeLog.target_type == "asset", ChangeLog.target_id == aid)
            .all()
        )
        actions = sorted(l.action for l in logs)
        assert actions == ["create", "delete", "update"]
        upd = next(l for l in logs if l.action == "update")
        assert (upd.field, upd.old_value, upd.new_value) == ("sn", "OLD-SN", "NEW-SN")
    finally:
        db.close()


# ---------- 字段来源保护（规则6） ----------


def test_manual_field_not_overwritten_by_import_source(crud_users):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.employee_no == "910001").first()
        asset = Asset(
            type="server",
            cabinet_id=crud_users["cab_admin"].id,
            u_start=40,
            u_end=40,
            sn="MANUAL-SN",
        )
        asset.field_source = {"sn": "manual"}
        db.add(asset)
        db.commit()
        db.refresh(asset)

        # import 来源不得覆盖 manual
        asset_service.update_asset(db, admin, asset.id, AssetUpdate(sn="IMPORT-SN"), source="import")
        db.refresh(asset)
        assert asset.sn == "MANUAL-SN"

        # manual 来源可正常覆盖
        asset_service.update_asset(db, admin, asset.id, AssetUpdate(sn="MANUAL-SN-2"), source="manual")
        db.refresh(asset)
        assert asset.sn == "MANUAL-SN-2"
    finally:
        db.close()


# ---------- 列表：过滤 + 定位上下文 ----------


def test_list_assets_filters_and_location(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        client.post(
            "/api/assets",
            json=_create_payload(cid, 41, 41, sn="SRV-1", model="Dell R740"),
            headers=h,
        )
        client.post(
            "/api/assets",
            json=_create_payload(cid, 42, 42, sn="SW-1", type="switch"),
            headers=h,
        )

        # 默认列表带机柜/机房定位
        r = client.get("/api/assets", headers=h)
        assert r.status_code == 200
        srv = next(a for a in r.json()["items"] if a["sn"] == "SRV-1")
        assert srv["cabinet_name"] == "T-A01-02"
        assert srv["room_code"] == "T-ROOM-1"

        # type 过滤
        r = client.get("/api/assets", params={"type": "switch"}, headers=h)
        assert [a["sn"] for a in r.json()["items"]] == ["SW-1"]

        # status 过滤（默认 in_use；无匹配返回空）
        r = client.get("/api/assets", params={"status": "in_use"}, headers=h)
        assert all(a["status"] == "in_use" for a in r.json()["items"])
        r = client.get("/api/assets", params={"status": "nope"}, headers=h)
        assert r.json()["total"] == 0

        # q 按型号搜索（新增字段 model）
        r = client.get("/api/assets", params={"q": "R740"}, headers=h)
        assert [a["sn"] for a in r.json()["items"]] == ["SRV-1"]


def test_list_assets_multivalue_filters(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        client.post(
            "/api/assets",
            json=_create_payload(cid, 41, 41, sn="SRV-ABC-1", model="Dell R740"),
            headers=h,
        )
        client.post(
            "/api/assets",
            json=_create_payload(cid, 42, 42, sn="SRV-XYZ-2", model="HPE DL380"),
            headers=h,
        )
        client.post(
            "/api/assets",
            json=_create_payload(cid, 43, 43, sn="SW-ABC-3", type="switch"),
            headers=h,
        )

        # 枚举列精确：types 多值 OR
        r = client.get(
            "/api/assets", params=[("types", "server"), ("types", "switch")], headers=h
        )
        assert r.json()["total"] == 3
        r = client.get("/api/assets", params=[("types", "switch")], headers=h)
        assert [a["sn"] for a in r.json()["items"]] == ["SW-ABC-3"]

        # 文本列包含：sns 命中「ABC」子串（列内 OR）
        r = client.get("/api/assets", params=[("sns", "ABC")], headers=h)
        assert sorted(a["sn"] for a in r.json()["items"]) == ["SRV-ABC-1", "SW-ABC-3"]

        # 多列 AND：类型精确 + SN 包含
        r = client.get(
            "/api/assets", params=[("types", "server"), ("sns", "XYZ")], headers=h
        )
        assert [a["sn"] for a in r.json()["items"]] == ["SRV-XYZ-2"]


def test_assets_facets(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        client.post(
            "/api/assets", json=_create_payload(cid, 41, 41, sn="SRV-1", model="R740"), headers=h
        )
        client.post(
            "/api/assets", json=_create_payload(cid, 42, 42, sn="SW-1", type="switch"), headers=h
        )

        r = client.get("/api/assets/facets", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert {f["value"]: f["count"] for f in body["type"]} == {"server": 1, "switch": 1}
        assert {f["value"]: f["count"] for f in body["model"]}["R740"] == 1
        assert {f["value"]: f["count"] for f in body["room_code"]}["T-ROOM-1"] == 2
        assert {f["value"]: f["count"] for f in body["cabinet_name"]}["T-A01-02"] == 2


def test_asset_remark_filter_and_facet(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        cid = crud_users["cab_admin"].id
        client.post(
            "/api/assets",
            json=_create_payload(cid, 21, 21, sn="SRV-RM-1", remark="报废待处理"),
            headers=h,
        )
        client.post(
            "/api/assets",
            json=_create_payload(cid, 22, 22, sn="SRV-RM-2", remark="正常"),
            headers=h,
        )

        # 备注包含匹配（列内 OR）
        r = client.get("/api/assets", params=[("remarks", "报废")], headers=h)
        assert [a["sn"] for a in r.json()["items"]] == ["SRV-RM-1"]

        # facet 带备注列
        r = client.get("/api/assets/facets", headers=h)
        assert {f["value"]: f["count"] for f in r.json()["remark"]} == {"报废待处理": 1, "正常": 1}
