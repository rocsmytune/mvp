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


def test_component_manual_fields_name_material_holder(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _create_asset(client, h, crud_users["cab_admin"].id, 33, 33)
        resp = client.post(
            "/api/components",
            json={
                "asset_id": asset["id"],
                "category": "内存",
                "sn": "MEM-2",
                "name": "DDR4内存条",
                "material_code": "MAT-001",
                "holder_name": "张三",
            },
            headers=h,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "DDR4内存条"
        assert body["material_code"] == "MAT-001"
        assert body["holder_name"] == "张三"

        r = client.patch(
            f"/api/components/{body['id']}",
            json={"material_code": "MAT-002", "holder_name": "李四"},
            headers=h,
        )
        assert r.status_code == 200
        assert r.json()["material_code"] == "MAT-002"
        assert r.json()["holder_name"] == "李四"


def test_component_holder_resolves_employee_no(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _create_asset(client, h, crud_users["cab_admin"].id, 34, 34)

        # 工号命中 → 关联 holder_id，姓名以输入为准
        r = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "HDD-1", "holder_name": "910002 张三"},
            headers=h,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["holder_id"] == crud_users["owner"].id
        assert body["holder_name"] == "张三"

        # 列表回显 holder_employee_no，供编辑表单还原「工号 姓名」
        r = client.get("/api/components", params={"asset_id": asset["id"]}, headers=h)
        item = next(c for c in r.json()["items"] if c["sn"] == "HDD-1")
        assert item["holder_employee_no"] == "910002"

        # 工号未命中 → 存原文、holder_id 为空
        r = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "HDD-2", "holder_name": "999999 李四"},
            headers=h,
        )
        assert r.status_code == 201
        assert r.json()["holder_id"] is None
        assert r.json()["holder_name"] == "999999 李四"

        # 纯姓名未命中库 → 不关联、存原文
        r = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "HDD-3", "holder_name": "王五"},
            headers=h,
        )
        assert r.status_code == 201
        assert r.json()["holder_id"] is None
        assert r.json()["holder_name"] == "王五"

        # 编辑：用「工号 姓名」更新关联到另一用户
        r = client.patch(
            f"/api/components/{body['id']}", json={"holder_name": "910003 王五"}, headers=h
        )
        assert r.status_code == 200
        assert r.json()["holder_id"] == crud_users["member"].id
        assert r.json()["holder_name"] == "王五"


def test_component_holder_pure_name_matches(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = _create_asset(client, h, crud_users["cab_admin"].id, 35, 35)

        # 纯姓名唯一命中 → 关联对应用户
        r = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "HDD-4", "holder_name": "测试柜主"},
            headers=h,
        )
        assert r.status_code == 201
        assert r.json()["holder_id"] == crud_users["owner"].id
        assert r.json()["holder_name"] == "测试柜主"

        # 姓名在前格式也能识别
        r = client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "HDD-5", "holder_name": "测试成员910003"},
            headers=h,
        )
        assert r.status_code == 201
        assert r.json()["holder_id"] == crud_users["member"].id
        assert r.json()["holder_name"] == "测试成员"


def test_list_components_filters_and_location(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = client.post(
            "/api/assets",
            json={
                "type": "server",
                "cabinet_id": crud_users["cab_admin"].id,
                "u_start": 32,
                "u_end": 32,
                "sn": "PARENT-SN",
                "model": "SR650",
            },
            headers=h,
        ).json()
        client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "CPU", "sn": "CPU-SN-1"},
            headers=h,
        )
        client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "内存", "sn": "MEM-SN-1", "model": "DDR4-32G"},
            headers=h,
        )

        # 默认列表带父资产/机柜/机房定位
        r = client.get("/api/components", headers=h)
        assert r.status_code == 200
        cpu = next(c for c in r.json()["items"] if c["sn"] == "CPU-SN-1")
        assert cpu["asset_sn"] == "PARENT-SN"
        assert cpu["asset_model"] == "SR650"
        assert cpu["cabinet_id"] == crud_users["cab_admin"].id
        assert cpu["cabinet_name"] == "T-A01-02"
        assert cpu["room_code"] == "T-ROOM-1"

        # category 过滤
        r = client.get("/api/components", params={"category": "内存"}, headers=h)
        assert [c["sn"] for c in r.json()["items"]] == ["MEM-SN-1"]

        # q 按型号搜索
        r = client.get("/api/components", params={"q": "DDR4"}, headers=h)
        assert [c["sn"] for c in r.json()["items"]] == ["MEM-SN-1"]


def test_list_components_multivalue_filters(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = client.post(
            "/api/assets",
            json={
                "type": "server",
                "cabinet_id": crud_users["cab_admin"].id,
                "u_start": 32,
                "u_end": 32,
                "sn": "PARENT-SN",
                "model": "SR650",
            },
            headers=h,
        ).json()
        client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "内存", "sn": "MEM-AA-1", "material_code": "MAT-X"},
            headers=h,
        )
        client.post(
            "/api/components",
            json={"asset_id": asset["id"], "category": "硬盘", "sn": "DISK-BB-1", "material_code": "MAT-Y"},
            headers=h,
        )

        # 枚举列精确：categories 多值
        r = client.get("/api/components", params=[("categories", "内存")], headers=h)
        assert [c["sn"] for c in r.json()["items"]] == ["MEM-AA-1"]

        # 文本列包含：sns 命中「BB」子串
        r = client.get("/api/components", params=[("sns", "BB")], headers=h)
        assert [c["sn"] for c in r.json()["items"]] == ["DISK-BB-1"]

        # 多列 AND：物料类型精确 + 物料编码包含
        r = client.get(
            "/api/components",
            params=[("categories", "硬盘"), ("material_codes", "MAT-Y")],
            headers=h,
        )
        assert [c["sn"] for c in r.json()["items"]] == ["DISK-BB-1"]


def test_components_facets(crud_users):
    with TestClient(app) as client:
        h = _auth(client, "910001", "admin-pass")
        asset = client.post(
            "/api/assets",
            json={
                "type": "server",
                "cabinet_id": crud_users["cab_admin"].id,
                "u_start": 32,
                "u_end": 32,
                "sn": "PARENT-SN",
                "model": "SR650",
            },
            headers=h,
        ).json()
        client.post("/api/components", json={"asset_id": asset["id"], "category": "内存", "sn": "MEM-1"}, headers=h)
        client.post("/api/components", json={"asset_id": asset["id"], "category": "硬盘", "sn": "DISK-1"}, headers=h)

        r = client.get("/api/components/facets", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert {f["value"]: f["count"] for f in body["category"]} == {"内存": 1, "硬盘": 1}
        assert {f["value"]: f["count"] for f in body["cabinet_name"]}["T-A01-02"] == 2
        assert {f["value"]: f["count"] for f in body["room_code"]}["T-ROOM-1"] == 2
