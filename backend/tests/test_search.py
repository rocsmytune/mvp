from fastapi.testclient import TestClient

from app.main import app


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _mk_asset(client, h, cabinet_id, **fields):
    payload = {"type": "server", "cabinet_id": cabinet_id, "u_start": 5, "u_end": 5}
    payload.update(fields)
    resp = client.post("/api/assets", json=payload, headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _search(client, h, q):
    resp = client.get("/api/search", params={"q": q}, headers=h)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_search_asset_by_key_fields(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        _mk_asset(
            client,
            h,
            crud_users["cab_owner"].id,
            sn="SRCH-SN-0001",
            asset_tag="TAG-0001",
            ip_inband="10.0.1.1",
            bmc_ip="10.0.0.1",
            model="SRV-X1",
        )

        cases = {
            "SRCH-SN-0001": "sn",
            "TAG-0001": "asset_tag",
            "10.0.1.1": "ip_inband",
            "10.0.0.1": "bmc_ip",
        }
        for q, field in cases.items():
            rows = _search(client, h, q)
            assert len(rows) == 1, f"q={q} -> {rows}"
            r = rows[0]
            assert r["kind"] == "asset"
            assert r["matched_field"] == field
            # 定位：机房-机柜-U位-柜主
            assert r["room_code"] == "T-ROOM-1"
            assert r["cabinet_name"] == "T-A01-01"
            assert r["owner_name"] == "测试柜主"
            assert (r["u_start"], r["u_end"]) == (5, 5)

        # 关键字大小写不敏感 + 部分匹配
        rows = _search(client, h, "srch-sn")
        assert len(rows) == 1 and rows[0]["matched_field"] == "sn"


def test_search_component_sn(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _mk_asset(client, h, crud_users["cab_owner"].id, sn="SRCH-PARENT-1")
        comp = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "SRCH-COMP-0001"},
            headers=h,
        )
        assert comp.status_code == 201, comp.text

        rows = _search(client, h, "SRCH-COMP-0001")
        assert len(rows) == 1
        r = rows[0]
        assert r["kind"] == "component"
        assert r["matched_field"] == "component_sn"
        assert r["component_id"] == comp.json()["id"]
        assert r["component_sn"] == "SRCH-COMP-0001"
        assert r["component_category"] == "硬盘"
        # 定位信息来自父整机
        assert r["asset_id"] == asset["id"]
        assert r["asset_sn"] == "SRCH-PARENT-1"
        assert r["cabinet_name"] == "T-A01-01"
        assert r["room_code"] == "T-ROOM-1"
        assert r["owner_name"] == "测试柜主"


def test_search_excludes_deleted(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _mk_asset(client, h, crud_users["cab_owner"].id, sn="SRCH-DEL-1")
        comp = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "内存", "sn": "SRCH-DEL-C-1"},
            headers=h,
        ).json()

        # 删除部件后不再命中；删除整机后资产不再命中
        assert client.delete(f"/api/components/{comp['id']}", headers=h).status_code == 204
        assert _search(client, h, "SRCH-DEL-C-1") == []
        assert client.delete(f"/api/assets/{asset['id']}", headers=h).status_code == 204
        assert _search(client, h, "SRCH-DEL-1") == []


def test_search_readable_by_member(crud_users):
    with TestClient(app) as client:
        admin_h = _auth(client, "910001", "admin-pass")
        _mk_asset(client, admin_h, crud_users["cab_admin"].id, sn="SRCH-MEMBER-1")
        member_h = _auth(client, "910003", "member-pass")
        rows = _search(client, member_h, "SRCH-MEMBER-1")
        assert len(rows) == 1


def test_search_blank_returns_empty(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        # 空白关键字：服务层返回空列表
        assert _search(client, h, "   ") == []
        # 缺少 q：参数校验 422
        resp = client.get("/api/search", headers=h)
        assert resp.status_code == 422
