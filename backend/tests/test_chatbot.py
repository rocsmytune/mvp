"""AI 助手（chatbot）对话测试。monkeypatch LLM 客户端，不发起真实网络请求。"""

import json

import httpx
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models.asset import Asset
from app.models.llm_config import AppSetting, UserLlmConfig
from app.services import chatbot


def _auth(client, employee_no, password):
    resp = client.post(
        "/api/auth/login", json={"employee_no": employee_no, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _set_global(db, base_url="http://llm.local/v1", model="m", quota=50000):
    s = db.get(AppSetting, 1)
    if s is None:
        s = AppSetting(id=1)
        db.add(s)
    s.llm_base_url = base_url
    s.llm_model = model
    s.daily_token_quota = quota
    db.commit()
    db.refresh(s)
    return s


def _set_personal(db, user_id, base_url="http://p.local/v1", model="pm"):
    cfg = db.query(UserLlmConfig).filter(UserLlmConfig.user_id == user_id).first()
    if cfg is None:
        cfg = UserLlmConfig(user_id=user_id)
        db.add(cfg)
    cfg.llm_base_url = base_url
    cfg.llm_model = model
    cfg.enabled = True
    db.commit()
    db.refresh(cfg)
    return cfg


def _mock_invoke(monkeypatch, responses):
    calls = {"i": 0}

    def fake(config, messages, tools=None):
        idx = min(calls["i"], len(responses) - 1)
        calls["i"] += 1
        return responses[idx]

    monkeypatch.setattr(chatbot, "_invoke_llm", fake)


def _final(text):
    return {"choices": [{"message": {"role": "assistant", "content": text}}], "usage": {"total_tokens": 50}}


def _tool_call(name, args):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                    ],
                }
            }
        ],
        "usage": {"total_tokens": 100},
    }


# ---------- 基础 ----------


def test_chat_requires_auth():
    with TestClient(app) as client:
        resp = client.post("/api/chat", json={"message": "你好"})
    assert resp.status_code == 401


def test_chat_unconfigured_503(crud_users):
    db = SessionLocal()
    try:
        db.query(AppSetting).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "帮我找一台机器"}, headers=h)
    assert resp.status_code == 503


# ---------- 工具调用 / 知识库兜底 ----------


def test_chat_knowledge_fallback(crud_users, monkeypatch):
    db = SessionLocal()
    try:
        _set_global(db)
    finally:
        db.close()
    _mock_invoke(monkeypatch, [_final("导入物料需要先在机柜总览补录机器与 IP，再上传表格。")])
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "物料怎么导入？"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "补录" in body["reply"]
    assert body["hits"] == []


def test_chat_tool_call_returns_hits(crud_users, monkeypatch):
    db = SessionLocal()
    try:
        _set_global(db)
        # 造一台设备供 search_assets 命中
        asset = Asset(
            type="server",
            cabinet_id=crud_users["cab_admin"].id,
            u_start=1,
            u_end=2,
            sn="T-CHAT-SRV-01",
            bmc_ip="192.0.2.50",
        )
        db.add(asset)
        db.commit()
    finally:
        db.close()

    _mock_invoke(
        monkeypatch,
        [
            _tool_call("search_assets", {"q": "T-CHAT-SRV-01"}),
            _final("已找到 1 台设备，位于 T-A01-02 · U1-2。"),
        ],
    )
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "T-CHAT-SRV-01 在哪？"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "找到" in body["reply"]
    assert len(body["hits"]) == 1
    hit = body["hits"][0]
    assert hit["kind"] == "asset"
    assert hit["asset_sn"] == "T-CHAT-SRV-01"
    assert hit["cabinet_id"] == crud_users["cab_admin"].id


def test_chat_unknown_tool_ignored(crud_users, monkeypatch):
    """LLM 请求了白名单外的工具：不执行、不崩溃，仍返回最终回答。"""
    db = SessionLocal()
    try:
        _set_global(db)
    finally:
        db.close()
    _mock_invoke(
        monkeypatch,
        [_tool_call("drop_all_tables", {}), _final("抱歉，我无法执行该操作。")],
    )
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "删掉所有数据"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["hits"] == []


# ---------- 配额 ----------


def test_chat_quota_exceeded_429(crud_users, monkeypatch):
    from datetime import date

    from app.models.llm_config import LlmUsage

    db = SessionLocal()
    try:
        _set_global(db, quota=10)
        db.add(LlmUsage(user_id=crud_users["member"].id, usage_date=date.today(), tokens_used=10))
        db.commit()
    finally:
        db.close()
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "帮我查一台机器"}, headers=h)
    assert resp.status_code == 429


def test_chat_personal_key_exempts_quota(crud_users, monkeypatch):
    from datetime import date

    from app.models.llm_config import LlmUsage

    db = SessionLocal()
    try:
        _set_global(db, quota=10)
        _set_personal(db, crud_users["member"].id)
        # 默认 API 额度已满，但个人配置齐全 → 走个人、免配额
        db.add(LlmUsage(user_id=crud_users["member"].id, usage_date=date.today(), tokens_used=10))
        db.commit()
    finally:
        db.close()
    _mock_invoke(monkeypatch, [_final("已处理。")])
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "帮我查一台机器"}, headers=h)
    assert resp.status_code == 200


# ---------- 服务异常 ----------


def test_chat_llm_http_error_502(crud_users, monkeypatch):
    db = SessionLocal()
    try:
        _set_global(db)
    finally:
        db.close()

    def boom(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(chatbot, "_call_llm", boom)
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "帮我查一台机器"}, headers=h)
    assert resp.status_code == 502


# ---------- 第二批工具：盘点统计 / 变更追溯 ----------


def test_tool_handlers_registered():
    """三批能力对应的工具均已注册到白名单。"""
    assert {"count_assets", "count_components", "query_changelogs"}.issubset(
        chatbot.TOOL_HANDLERS
    )


def test_tool_count_assets(crud_users):
    from app.models.asset import Asset

    db = SessionLocal()
    try:
        cab = crud_users["cab_admin"]
        db.add(
            Asset(
                type="server", cabinet_id=cab.id, u_start=1, u_end=2,
                sn="T-STAT-SRV-01", status="in_use",
            )
        )
        db.add(
            Asset(
                type="server", cabinet_id=cab.id, u_start=3, u_end=3,
                sn="T-STAT-SRV-02", status="repair",
            )
        )
        db.add(
            Asset(
                type="switch", cabinet_id=cab.id, u_start=4, u_end=4,
                sn="T-STAT-SW-01", status="in_use",
            )
        )
        # 待整理池设备（cabinet_id 为空 → u 位为空，in_pool）
        db.add(
            Asset(
                type="server", cabinet_id=None, u_start=None, u_end=None,
                sn="T-POOL-STAT-01", status="in_use", in_pool=True,
            )
        )
        db.commit()

        ans = chatbot._tool_count_assets(db)["answer"]
        assert ans["设备总数"] == 4
        assert ans["上架"] == 3
        assert ans["待整理池"] == 1
        assert ans["按类型"] == {"服务器": 3, "交换机": 1}
        assert ans["按状态"] == {"in_use": 3, "repair": 1}

        # 按类型过滤
        ans2 = chatbot._tool_count_assets(db, asset_type="server")["answer"]
        assert ans2["设备总数"] == 3
        assert ans2["按类型"] == {"服务器": 3}
        assert ans2["待整理池"] == 1
    finally:
        db.close()


def test_tool_count_components(crud_users):
    from app.models.asset import Asset
    from app.models.component import Component

    db = SessionLocal()
    try:
        cab = crud_users["cab_admin"]
        asset = Asset(
            type="server", cabinet_id=cab.id, u_start=1, u_end=1, sn="T-STAT-SRV-01"
        )
        db.add(asset)
        db.flush()
        db.add(Component(asset_id=asset.id, category="硬盘", sn="T-STAT-HDD-01", qty=1))
        db.add(Component(asset_id=asset.id, category="硬盘", sn=None, qty=5, name="硬盘-数量件"))
        db.add(Component(asset_id=asset.id, category="内存", sn="T-STAT-RAM-01", qty=1))
        db.commit()

        ans = chatbot._tool_count_components(db)["answer"]
        assert ans["部件记录数"] == 3
        assert ans["部件总数量"] == 7
        assert ans["按类型"]["硬盘"] == {"记录数": 2, "数量": 6}
        assert ans["按类型"]["内存"] == {"记录数": 1, "数量": 1}

        ans2 = chatbot._tool_count_components(db, category="硬盘")["answer"]
        assert ans2["部件记录数"] == 2
        assert ans2["部件总数量"] == 6
    finally:
        db.close()


def test_tool_query_changelogs(crud_users):
    from app.models.asset import Asset
    from app.models.change_log import ChangeLog

    db = SessionLocal()
    try:
        cab = crud_users["cab_admin"]
        asset = Asset(
            type="server", cabinet_id=cab.id, u_start=1, u_end=1, sn="T-STAT-SRV-01"
        )
        db.add(asset)
        db.flush()
        db.add(
            ChangeLog(
                target_type="asset", target_id=asset.id, cabinet_id=cab.id,
                action="update", field="bmc_ip", old_value="", new_value="192.0.2.60",
                operator_id=crud_users["admin"].id, source="manual",
            )
        )
        db.add(
            ChangeLog(
                target_type="asset", target_id=asset.id, cabinet_id=cab.id,
                action="create", field=None, old_value=None, new_value=None,
                operator_id=crud_users["admin"].id, source="import",
            )
        )
        db.commit()

        # 按 SN 定位追溯
        ans = chatbot._tool_query_changelogs(db, q="T-STAT-SRV-01")["answer"]
        assert ans["变更条数"] == 2
        top = ans["变更"][0]
        assert top["对象"] == "设备"
        assert top["对象标识"] == "T-STAT-SRV-01"
        assert top["操作人"] == "测试物料管理员"

        # 按动作筛选
        ans2 = chatbot._tool_query_changelogs(db, q="T-STAT-SRV-01", action="create")["answer"]
        assert ans2["变更条数"] == 1
        assert ans2["变更"][0]["动作"] == "新增"
        assert ans2["变更"][0]["来源"] == "import"

        # 定位不到的目标
        ans3 = chatbot._tool_query_changelogs(db, q="NOT-EXIST-X")["answer"]
        assert "未找到" in ans3["提示"]
    finally:
        db.close()


def test_chat_count_assets_tool(crud_users, monkeypatch):
    """端点级：LLM 请求 count_assets 工具时，白名单执行且返回结构化统计。"""
    db = SessionLocal()
    try:
        _set_global(db)
    finally:
        db.close()
    _mock_invoke(
        monkeypatch,
        [
            _tool_call("count_assets", {}),
            _final("当前共 4 台设备，其中服务器 3 台、交换机 1 台。"),
        ],
    )
    with TestClient(app) as client:
        h = _auth(client, "910003", "member-pass")
        resp = client.post("/api/chat", json={"message": "盘点一下设备数量"}, headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert "服务器" in body["reply"]
    assert body["hits"] == []
