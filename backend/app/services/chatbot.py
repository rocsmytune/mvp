"""AI 助手（chatbot）：自然语言检索/统计/追溯/答疑。**只读**，不通过对话改库。

设计（见 docs/进度.md §A）：
- 混合检索：工具调用实时查库为主，知识库兜底回答使用类问题。
- 准确性：LLM 只「听懂问题 + 抽参数 + 组织语言」，事实 100% 来自工具查库；命中项 hits[]
  结构化返回由前端渲染，不靠 LLM 复述精确字段。
- 越界防护：工具白名单只读 + 服务端执行；系统提示词身份/话题锚定；敏感值不回显。
- 配额：走默认 API 时每用户每日 5 万 token（llm_usage 累计）；用个人 key 免平台配额。
"""

import json
from datetime import date

import httpx
from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.models.asset import Asset
from app.models.cabinet import Cabinet
from app.models.change_log import ChangeLog
from app.models.component import Component
from app.models.llm_config import AppSetting, LlmUsage, UserLlmConfig
from app.models.room import Room
from app.models.user import User

_GLOBAL_ID = 1
_MAX_HITS = 20
_MAX_TOOL_ROUNDS = 3

# ---------------------------------------------------------------------------
# 系统提示词：身份锚定 + 话题边界 + 事实锚定 + 知识库兜底
# ---------------------------------------------------------------------------

KNOWLEDGE_BASE = """平台使用说明（知识库，回答「怎么用」类问题时据此回答）：
- 角色：系统管理员（全权含用户管理）、物料管理员（物料/机柜/导入/导出）、柜主（仅本机柜）、成员（只读）。
- 导入物料：手工物料表格导入，列 = BMC IP / 整机SN / 物料类型 / SN / 物料编码 / 物料名称 / 备注 / 挂账人。
  按 BMC IP 定位到机器与机柜；定位不到会在预览报错，需先在「机柜总览」补录机器与 IP 后重新导入。
- 物料类型 9 种：交换机、硬盘、内存、整机、主板、光模块、RAID、网卡、BMC插卡；整机/交换机=资产本身，其余挂到资产下作为部件。
- 部件挂账：有价值部件（硬盘/内存等）才挂账；服务器整机不挂账。
- 机柜规则：45U，U1 在底部；同一机柜内未删除设备 U 位不重叠。
- 补录机器：在机柜总览新建资产，填写类型、SN、BMC IP 等字段。
"""

SYSTEM_PROMPT = (
    "你是「机柜物料管理平台」的内网智能助手，只回答与平台相关的问题：设备/部件/机柜的定位检索、"
    "盘点统计、变更追溯，以及平台使用帮助。\n"
    "规则：\n"
    "1. 需要查实时数据时，必须调用提供的工具，且只依据工具返回结果回答，不得臆测、补充或编造。\n"
    "2. 工具查不到时，如实说「未找到」，并给可能的下一步建议（如核对 SN/IP、先在机柜总览补录机器与IP）。\n"
    "3. 精确字段（SN、IP、U位、机柜名、数量）必须逐字引用工具返回的值，不得改写或省略。\n"
    "4. 用户问题信息不足时，反问澄清关键参数（BMC IP、整机SN、物料类型、机柜名等）。\n"
    "5. 与平台无关的问题（闲聊、编程、翻译、天气等）一律礼貌拒绝：「抱歉，我是机柜物料管理平台的助手，"
    "只能回答平台相关的问题」，并引导用户询问平台能提供的帮助。\n"
    "6. 用中文回答，简洁、结构化；命中多台设备时列出关键定位信息（机房-机柜-U位）。\n\n"
    f"{KNOWLEDGE_BASE}"
)


def _get_setting(db: Session) -> AppSetting:
    """获取（或惰性创建）全局配置单行。"""
    s = db.get(AppSetting, _GLOBAL_ID)
    if s is None:
        s = AppSetting(id=_GLOBAL_ID)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _resolve_config(db: Session, user: User) -> tuple[dict | None, bool]:
    """解析生效配置。

    返回 (config, use_personal)。config = {base_url, api_key, model}；未配置返回 (None, False)。
    个人配置（enabled 且 base_url+model 齐全）优先，否则回退全局默认。
    """
    cfg = db.query(UserLlmConfig).filter(UserLlmConfig.user_id == user.id).first()
    if cfg and cfg.enabled and cfg.llm_base_url and cfg.llm_model:
        api_key = decrypt_secret(cfg.llm_api_key_enc) if cfg.llm_api_key_enc else None
        return {
            "base_url": cfg.llm_base_url,
            "api_key": api_key,
            "model": cfg.llm_model,
        }, True

    s = _get_setting(db)
    if s.llm_base_url and s.llm_model:
        api_key = decrypt_secret(s.llm_api_key_enc) if s.llm_api_key_enc else None
        return {"base_url": s.llm_base_url, "api_key": api_key, "model": s.llm_model}, False
    return None, False


# ---------------------------------------------------------------------------
# 配额（仅默认 API 受配额，个人 key 免配额）
# ---------------------------------------------------------------------------

DEFAULT_DAILY_QUOTA = 50000


def _today_usage(db: Session, user_id: int) -> int:
    row = (
        db.query(LlmUsage)
        .filter(LlmUsage.user_id == user_id, LlmUsage.usage_date == date.today())
        .first()
    )
    return row.tokens_used if row else 0


def _add_usage(db: Session, user_id: int, tokens: int) -> None:
    if tokens <= 0:
        return
    row = (
        db.query(LlmUsage)
        .filter(LlmUsage.user_id == user_id, LlmUsage.usage_date == date.today())
        .first()
    )
    if row is None:
        db.add(LlmUsage(user_id=user_id, usage_date=date.today(), tokens_used=tokens))
    else:
        row.tokens_used += tokens


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

def _call_llm(config: dict, messages: list, tools: list | None = None) -> dict:
    base = config["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"
    body: dict = {"model": config["model"], "messages": messages, "temperature": 0}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(f"{base}/chat/completions", json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _extract_tokens(resp: dict, messages: list) -> int:
    """从 usage 提取本次消耗 token；无 usage 字段时按字符粗略估算。"""
    usage = resp.get("usage") or {}
    if usage.get("total_tokens") is not None:
        return int(usage["total_tokens"])
    if usage.get("prompt_tokens") is not None or usage.get("completion_tokens") is not None:
        return int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
    chars = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    return int(chars / 4)


def _invoke_llm(config: dict, messages: list, tools: list | None = None) -> dict:
    """调用 LLM；端点不支持 tools 时降级为纯对话；网络/服务错误转友好 502。"""
    try:
        return _call_llm(config, messages, tools=tools)
    except httpx.HTTPStatusError:
        if tools is None:
            raise HTTPException(status_code=502, detail="AI 助手服务返回错误，请稍后重试")
        try:  # 端点可能不支持 tools，降级为不带 tools 重试一次
            return _call_llm(config, messages)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="AI 助手服务不可用，请稍后重试") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="AI 助手服务不可用，请稍后重试") from exc


def _message_from_choice(resp: dict) -> dict:
    return resp["choices"][0]["message"]


# ---------------------------------------------------------------------------
# 工具：白名单只读，服务端执行
# ---------------------------------------------------------------------------

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_assets",
            "description": "按整机SN/带内IP/带外IP(BMC)/资产标签/型号/备注 检索服务器或交换机，返回定位（机房-机柜-U位-柜主）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "关键字，如 SN、BMC IP、资产标签"},
                    "asset_type": {"type": "string", "enum": ["server", "switch"]},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_components",
            "description": "按部件SN/物料名称/物料编码/备注 检索部件（硬盘、内存等），返回其所在整机与定位。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "关键字，如部件 SN 或物料名称"},
                    "category": {"type": "string", "description": "物料类型，如 硬盘/内存/网卡"},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_cabinets",
            "description": "按机房编码/区域/柜主姓名 列出机柜及其设备数与占用 U 数。",
            "parameters": {
                "type": "object",
                "properties": {
                    "room_code": {"type": "string"},
                    "zone": {"type": "string"},
                    "owner_name": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cabinet_detail",
            "description": "查看某机柜的详情：按 U 位列出其上架设备（SN/IP/U 区间/状态）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "机柜名，如 A01-02"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_detail",
            "description": "查看某设备的详情字段，及其下挂的部件列表（按 SN/IP 定位单个设备）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "整机SN / BMC IP / 带内IP / 资产标签"},
                },
                "required": ["q"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_assets",
            "description": "盘点统计设备（服务器/交换机）数量：可按类型、状态、机房、是否待整理池过滤，返回总数与分组统计。",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_type": {"type": "string", "enum": ["server", "switch"]},
                    "status": {"type": "string", "description": "设备状态，如 在用/停用/维修"},
                    "room_code": {"type": "string", "description": "机房编码，如 SHA-01"},
                    "in_pool": {"type": "boolean", "description": "是否只看待整理池"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_components",
            "description": "盘点统计部件（硬盘/内存/网卡等）数量：可按物料类型过滤，返回总数与按类型分组统计（记录数与数量合计）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "物料类型，如 硬盘/内存/网卡"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_changelogs",
            "description": "追溯变更记录：按 SN/IP 定位某设备或部件查看其变更历史，或按对象类型/动作/操作人筛选最近变更，返回时间、字段、前后值、操作人、来源。",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "设备/部件 SN 或 IP，定位要追溯的目标"},
                    "target_type": {"type": "string", "enum": ["asset", "component"]},
                    "action": {"type": "string", "enum": ["create", "update", "delete"]},
                    "operator_name": {"type": "string", "description": "操作人姓名"},
                    "limit": {"type": "integer", "description": "返回条数，默认 20"},
                },
            },
        },
    },
]


def _base_hit(asset: Asset, room_code, cabinet_name, owner_name, matched_field) -> dict:
    return {
        "kind": "asset",
        "matched_field": matched_field,
        "room_code": room_code,
        "cabinet_id": asset.cabinet_id,
        "cabinet_name": cabinet_name,
        "u_start": asset.u_start,
        "u_end": asset.u_end,
        "owner_name": owner_name,
        "asset_id": asset.id,
        "asset_type": asset.type,
        "asset_sn": asset.sn,
        "asset_tag": asset.asset_tag,
        "model": asset.model,
        "ip_inband": asset.ip_inband,
        "bmc_ip": asset.bmc_ip,
        "status": asset.status,
        "in_pool": asset.in_pool,
        "component_id": None,
        "component_category": None,
        "component_sn": None,
        "component_name": None,
    }


def _asset_join(db: Session, query):
    return (
        query.outerjoin(Cabinet, Cabinet.id == Asset.cabinet_id)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Cabinet.owner_id)
    )


def _tool_search_assets(db: Session, q: str, asset_type: str | None = None) -> dict:
    like = f"%{q}%"
    query = _asset_join(
        db,
        db.query(Asset, Room.code, Cabinet.name, User.name).filter(
            Asset.deleted_at.is_(None),
            or_(
                Asset.sn.ilike(like),
                Asset.asset_tag.ilike(like),
                Asset.ip_inband.ilike(like),
                Asset.bmc_ip.ilike(like),
                Asset.model.ilike(like),
                Asset.remark.ilike(like),
            ),
        ),
    )
    if asset_type:
        query = query.filter(Asset.type == asset_type)
    rows = query.order_by(Asset.id.desc()).limit(_MAX_HITS).all()

    hits = []
    items = []
    for asset, room_code, cabinet_name, owner_name in rows:
        hits.append(_base_hit(asset, room_code, cabinet_name, owner_name, "sn"))
        items.append(
            {
                "类型": "服务器" if asset.type == "server" else "交换机",
                "SN": asset.sn,
                "资产标签": asset.asset_tag,
                "型号": asset.model,
                "带内IP": asset.ip_inband,
                "BMC IP": asset.bmc_ip,
                "位置": f"{room_code or '—'}·{cabinet_name or '待整理池'}·U{asset.u_start}-{asset.u_end}",
                "状态": asset.status,
            }
        )
    answer = {"匹配设备数": len(items), "设备": items} if items else {"匹配设备数": 0, "提示": "未找到"}
    return {"answer": answer, "_hits": hits}


def _tool_search_components(db: Session, q: str, category: str | None = None) -> dict:
    like = f"%{q}%"
    query = _asset_join(
        db,
        db.query(Component, Asset, Room.code, Cabinet.name, User.name)
        .join(Asset, Asset.id == Component.asset_id)
        .filter(
            Component.deleted_at.is_(None),
            Asset.deleted_at.is_(None),
            or_(
                Component.sn.ilike(like),
                Component.name.ilike(like),
                Component.material_code.ilike(like),
                Component.remark.ilike(like),
            ),
        ),
    )
    if category:
        query = query.filter(Component.category == category)
    rows = query.order_by(Component.id.desc()).limit(_MAX_HITS).all()

    hits = []
    items = []
    for comp, asset, room_code, cabinet_name, owner_name in rows:
        hit = _base_hit(asset, room_code, cabinet_name, owner_name, "component_sn")
        hit.update(
            {
                "kind": "component",
                "component_id": comp.id,
                "component_category": comp.category,
                "component_sn": comp.sn,
                "component_name": comp.name,
            }
        )
        hits.append(hit)
        items.append(
            {
                "物料类型": comp.category,
                "部件SN": comp.sn,
                "物料名称": comp.name,
                "物料编码": comp.material_code,
                "所在整机SN": asset.sn,
                "位置": f"{room_code or '—'}·{cabinet_name or '待整理池'}·U{asset.u_start}-{asset.u_end}",
                "挂账人": comp.holder_name,
            }
        )
    answer = {"匹配部件数": len(items), "部件": items} if items else {"匹配部件数": 0, "提示": "未找到"}
    return {"answer": answer, "_hits": hits}


def _tool_list_cabinets(
    db: Session, room_code: str | None = None, zone: str | None = None, owner_name: str | None = None
) -> dict:
    query = (
        db.query(Cabinet, Room, User)
        .outerjoin(Room, Room.id == Cabinet.room_id)
        .outerjoin(User, User.id == Cabinet.owner_id)
        .filter(Cabinet.deleted_at.is_(None))
    )
    if room_code:
        query = query.filter(Room.code.ilike(f"%{room_code}%"))
    if zone:
        query = query.filter(Room.zone.ilike(f"%{zone}%"))
    if owner_name:
        query = query.filter(User.name.ilike(f"%{owner_name}%"))
    rows = query.order_by(Cabinet.id).limit(_MAX_HITS).all()

    cab_ids = [c.id for c, _, _ in rows]
    used_map = {}
    count_map = {}
    if cab_ids:
        for cab_id, cnt, used in (
            db.query(
                Asset.cabinet_id,
                func.count(Asset.id),
                func.coalesce(func.sum(Asset.u_end - Asset.u_start + 1), 0),
            )
            .filter(Asset.deleted_at.is_(None), Asset.cabinet_id.in_(cab_ids))
            .group_by(Asset.cabinet_id)
            .all()
        ):
            used_map[cab_id] = used
            count_map[cab_id] = cnt

    items = []
    for cab, room, owner in rows:
        items.append(
            {
                "机柜": cab.name,
                "机房": room.code if room else None,
                "区域": room.zone if room else None,
                "柜主": owner.name if owner else "未指派",
                "设备数": count_map.get(cab.id, 0),
                "占用U": used_map.get(cab.id, 0),
            }
        )
    answer = {"机柜数": len(items), "机柜": items} if items else {"机柜数": 0, "提示": "未找到"}
    return {"answer": answer, "_hits": []}


def _tool_get_cabinet_detail(db: Session, name: str) -> dict:
    cab = (
        db.query(Cabinet).filter(Cabinet.deleted_at.is_(None), Cabinet.name == name).first()
    )
    if cab is None:
        return {"answer": {"提示": f"未找到机柜 {name}"}, "_hits": []}
    room = db.get(Room, cab.room_id)
    owner = db.get(User, cab.owner_id) if cab.owner_id else None

    assets = (
        db.query(Asset)
        .filter(Asset.deleted_at.is_(None), Asset.cabinet_id == cab.id)
        .order_by(Asset.u_start)
        .all()
    )
    hits = []
    devs = []
    for a in assets:
        hits.append(_base_hit(a, room.code if room else None, cab.name, owner.name if owner else None, "sn"))
        devs.append(
            {
                "U位": f"{a.u_start}-{a.u_end}" if a.u_start is not None else "待定",
                "类型": "服务器" if a.type == "server" else "交换机",
                "SN": a.sn,
                "BMC IP": a.bmc_ip,
                "状态": a.status,
            }
        )
    answer = {
        "机柜": cab.name,
        "机房": room.code if room else None,
        "柜主": owner.name if owner else "未指派",
        "设备数": len(devs),
        "设备": devs,
    }
    return {"answer": answer, "_hits": hits}


def _tool_get_asset_detail(db: Session, q: str) -> dict:
    like = f"%{q}%"
    row = _asset_join(
        db,
        db.query(Asset, Room.code, Cabinet.name, User.name).filter(
            Asset.deleted_at.is_(None),
            or_(
                Asset.sn.ilike(like),
                Asset.bmc_ip.ilike(like),
                Asset.ip_inband.ilike(like),
                Asset.asset_tag.ilike(like),
            ),
        ),
    ).first()
    if row is None:
        return {"answer": {"提示": f"未找到设备 {q}"}, "_hits": []}
    asset, room_code, cabinet_name, owner_name = row
    comps = (
        db.query(Component)
        .filter(Component.deleted_at.is_(None), Component.asset_id == asset.id)
        .order_by(Component.id)
        .all()
    )
    hits = [_base_hit(asset, room_code, cabinet_name, owner_name, "sn")]
    parts = [
        {
            "物料类型": c.category,
            "部件SN": c.sn,
            "物料名称": c.name,
            "数量": c.qty,
            "挂账人": c.holder_name,
        }
        for c in comps
    ]
    answer = {
        "类型": "服务器" if asset.type == "server" else "交换机",
        "SN": asset.sn,
        "资产标签": asset.asset_tag,
        "型号": asset.model,
        "CPU": asset.cpu_model,
        "带内IP": asset.ip_inband,
        "BMC IP": asset.bmc_ip,
        "位置": f"{room_code or '—'}·{cabinet_name or '待整理池'}·U{asset.u_start}-{asset.u_end}",
        "状态": asset.status,
        "部件数": len(parts),
        "部件": parts,
    }
    return {"answer": answer, "_hits": hits}


def _tool_count_assets(
    db: Session,
    asset_type: str | None = None,
    status: str | None = None,
    room_code: str | None = None,
    in_pool: bool | None = None,
) -> dict:
    conds = [Asset.deleted_at.is_(None)]
    if asset_type:
        conds.append(Asset.type == asset_type)
    if status:
        conds.append(Asset.status == status)
    if in_pool is not None:
        conds.append(Asset.in_pool.is_(in_pool))

    def scoped(join_room: bool = False):
        q = db.query(Asset).filter(*conds)
        if room_code:
            q = (
                q.join(Cabinet, Cabinet.id == Asset.cabinet_id)
                .join(Room, Room.id == Cabinet.room_id)
                .filter(Room.code.ilike(f"%{room_code}%"))
            )
        elif join_room:
            q = q.join(Cabinet, Cabinet.id == Asset.cabinet_id).join(Room, Room.id == Cabinet.room_id)
        return q

    total = scoped().count()
    by_type = dict(
        scoped().with_entities(Asset.type, func.count(Asset.id)).group_by(Asset.type).all()
    )
    by_status = dict(
        scoped().with_entities(Asset.status, func.count(Asset.id)).group_by(Asset.status).all()
    )
    placed = scoped().filter(Asset.in_pool.is_(False)).count()
    pool = scoped().filter(Asset.in_pool.is_(True)).count()
    by_room = dict(
        scoped(join_room=True)
        .with_entities(Room.code, func.count(Asset.id))
        .group_by(Room.code)
        .all()
    )

    answer = {
        "设备总数": total,
        "上架": placed,
        "待整理池": pool,
        "按类型": {("服务器" if k == "server" else "交换机"): v for k, v in by_type.items()},
        "按状态": by_status,
        "按机房": by_room or None,
    }
    return {"answer": answer, "_hits": []}


def _tool_count_components(db: Session, category: str | None = None) -> dict:
    conds = [Component.deleted_at.is_(None), Asset.deleted_at.is_(None)]
    if category:
        conds.append(Component.category == category)

    def base():
        return db.query(Component).join(Asset, Asset.id == Component.asset_id).filter(*conds)

    total_records = base().count()
    total_qty = base().with_entities(func.coalesce(func.sum(Component.qty), 0)).scalar() or 0
    by_cat = {
        cat: {"记录数": cnt, "数量": int(qty)}
        for cat, cnt, qty in base()
        .with_entities(
            Component.category,
            func.count(Component.id),
            func.coalesce(func.sum(Component.qty), 0),
        )
        .group_by(Component.category)
        .all()
    }
    answer = {
        "部件记录数": total_records,
        "部件总数量": int(total_qty),
        "按类型": by_cat,
    }
    return {"answer": answer, "_hits": []}


def _target_labels(db: Session, logs: list[ChangeLog]) -> dict:
    """批量解析变更日志目标对象的标识（SN/名称/资产标签），避免 N+1。"""
    asset_ids = {lg.target_id for lg in logs if lg.target_type == "asset"}
    comp_ids = {lg.target_id for lg in logs if lg.target_type == "component"}
    labels: dict[tuple[str, int], str] = {}
    if asset_ids:
        for a in db.query(Asset).filter(Asset.id.in_(asset_ids)).all():
            labels[("asset", a.id)] = a.sn or a.asset_tag or a.model or f"#{a.id}"
    if comp_ids:
        for c in db.query(Component).filter(Component.id.in_(comp_ids)).all():
            labels[("component", c.id)] = c.sn or c.name or f"#{c.id}"
    return labels


def _tool_query_changelogs(
    db: Session,
    q: str | None = None,
    target_type: str | None = None,
    action: str | None = None,
    operator_name: str | None = None,
    limit: int = 20,
) -> dict:
    query = db.query(ChangeLog, User.name).outerjoin(User, User.id == ChangeLog.operator_id)

    if q:
        like = f"%{q}%"
        asset = (
            db.query(Asset)
            .filter(
                Asset.deleted_at.is_(None),
                or_(
                    Asset.sn.ilike(like),
                    Asset.bmc_ip.ilike(like),
                    Asset.ip_inband.ilike(like),
                    Asset.asset_tag.ilike(like),
                ),
            )
            .first()
        )
        if asset:
            query = query.filter(ChangeLog.target_type == "asset", ChangeLog.target_id == asset.id)
        else:
            comp = (
                db.query(Component)
                .filter(
                    Component.deleted_at.is_(None),
                    or_(Component.sn.ilike(like), Component.name.ilike(like)),
                )
                .first()
            )
            if comp:
                query = query.filter(
                    ChangeLog.target_type == "component", ChangeLog.target_id == comp.id
                )
            else:
                return {"answer": {"提示": f"未找到 {q} 对应的设备或部件，无法追溯变更"}, "_hits": []}

    if target_type:
        query = query.filter(ChangeLog.target_type == target_type)
    if action:
        query = query.filter(ChangeLog.action == action)
    if operator_name:
        query = query.filter(User.name.ilike(f"%{operator_name}%"))

    rows = (
        query.order_by(ChangeLog.created_at.desc(), ChangeLog.id.desc())
        .limit(min(max(limit, 1), 50))
        .all()
    )

    labels = _target_labels(db, [lg for lg, _ in rows])
    action_map = {"create": "新增", "update": "修改", "delete": "删除"}
    items = []
    for lg, op_name in rows:
        items.append(
            {
                "时间": lg.created_at.isoformat() if lg.created_at else None,
                "对象": "设备" if lg.target_type == "asset" else "部件",
                "对象标识": labels.get((lg.target_type, lg.target_id), f"#{lg.target_id}"),
                "动作": action_map.get(lg.action, lg.action),
                "字段": lg.field,
                "旧值": lg.old_value,
                "新值": lg.new_value,
                "操作人": op_name or ("系统/导入" if lg.source != "manual" else "未知"),
                "来源": lg.source,
            }
        )
    answer = (
        {"变更条数": len(items), "变更": items}
        if items
        else {"变更条数": 0, "提示": "暂无变更记录"}
    )
    return {"answer": answer, "_hits": []}


TOOL_HANDLERS = {
    "search_assets": _tool_search_assets,
    "search_components": _tool_search_components,
    "list_cabinets": _tool_list_cabinets,
    "get_cabinet_detail": _tool_get_cabinet_detail,
    "get_asset_detail": _tool_get_asset_detail,
    "count_assets": _tool_count_assets,
    "count_components": _tool_count_components,
    "query_changelogs": _tool_query_changelogs,
}


def _run_tool(name: str, args: dict, db: Session) -> dict:
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return {"error": f"未知工具 {name}"}
    try:
        return handler(db, **args)
    except TypeError:
        return {"error": f"工具 {name} 参数不合法"}
    except HTTPException:
        raise
    except Exception as exc:  # 工具执行异常不外泄细节，回传给 LLM 一句失败
        return {"error": f"工具 {name} 执行失败"}


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def chat(db: Session, user: User, message: str) -> dict:
    message = (message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="请输入问题")

    config, use_personal = _resolve_config(db, user)
    if config is None:
        raise HTTPException(
            status_code=503,
            detail="AI 助手未配置，请联系系统管理员配置默认 API，或在「我的配置」中配置个人 API",
        )

    quota = _get_setting(db).daily_token_quota
    if not use_personal and _today_usage(db, user.id) >= quota:
        raise HTTPException(
            status_code=429,
            detail=f"今日默认 API 额度（{quota} token）已用尽，请配置个人 API 或明日再试",
        )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    total_tokens = 0
    hits: list[dict] = []

    # 第一轮：带工具（端点在支持 tools 时返回 tool_calls，否则直接给最终回答）
    resp = _invoke_llm(config, messages, tools=TOOL_SPECS)
    total_tokens += _extract_tokens(resp, messages)
    msg = _message_from_choice(resp)
    tool_calls = msg.get("tool_calls")

    if tool_calls:
        messages.append(
            {
                "role": "assistant",
                "content": msg.get("content"),
                "tool_calls": tool_calls,
            }
        )
        for tc in tool_calls[: _MAX_TOOL_ROUNDS]:
            fn = tc.get("function") or {}
            name = fn.get("name")
            raw_args = fn.get("arguments") or "{}"
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
            else:
                args = raw_args
            if not isinstance(args, dict):
                args = {}
            result = _run_tool(name, args, db)
            hits.extend(result.pop("_hits", []) or [])
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id") or name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        # 第二轮：不带 tools，让 LLM 基于工具结果生成最终回答
        resp2 = _invoke_llm(config, messages)
        total_tokens += _extract_tokens(resp2, messages)
        reply = _message_from_choice(resp2).get("content") or ""
    else:
        reply = msg.get("content") or ""

    if not use_personal:
        _add_usage(db, user.id, total_tokens)
        db.commit()

    # 命中去重（按 asset_id+component_id）并限制条数
    seen = set()
    deduped = []
    for h in hits:
        key = (h.get("asset_id"), h.get("component_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(h)
    return {"reply": reply, "hits": deduped[:_MAX_HITS]}
