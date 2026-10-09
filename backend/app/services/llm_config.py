"""AI 助手 LLM 配置：全局默认（system_admin）+ 个人覆盖 + 连通性测试。"""

import httpx
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.models.llm_config import AppSetting, UserLlmConfig
from app.models.user import User
from app.permissions import require_system_admin
from app.schemas.llm_config import (
    GlobalConfigOut,
    GlobalConfigUpdate,
    PersonalConfigOut,
    PersonalConfigUpdate,
)

# 全局配置固定单行，id 恒为 1。
_GLOBAL_ID = 1


def _configured(base_url: str | None, model: str | None) -> bool:
    """是否已配齐（base_url + model 均非空；api_key 对内网端点可选）。"""
    return bool(base_url and model)


def _get_setting(db: Session) -> AppSetting:
    """获取（或创建）全局配置单行。"""
    s = db.get(AppSetting, _GLOBAL_ID)
    if s is None:
        s = AppSetting(id=_GLOBAL_ID)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _global_out(s: AppSetting) -> GlobalConfigOut:
    api_key = decrypt_secret(s.llm_api_key_enc) if s.llm_api_key_enc else None
    return GlobalConfigOut(
        base_url=s.llm_base_url,
        model=s.llm_model,
        api_key_masked=mask_secret(api_key),
        daily_token_quota=s.daily_token_quota,
        configured=_configured(s.llm_base_url, s.llm_model),
    )


def get_global(db: Session) -> GlobalConfigOut:
    return _global_out(_get_setting(db))


def update_global(db: Session, operator: User, data: GlobalConfigUpdate) -> GlobalConfigOut:
    require_system_admin(operator)
    s = _get_setting(db)
    payload = data.model_dump(exclude_unset=True)

    if "api_key" in payload:
        key = payload.pop("api_key")
        s.llm_api_key_enc = encrypt_secret(key) if key else None
    if "base_url" in payload:
        s.llm_base_url = payload["base_url"] or None
    if "model" in payload:
        s.llm_model = payload["model"] or None
    if "daily_token_quota" in payload:
        s.daily_token_quota = payload["daily_token_quota"]

    db.commit()
    db.refresh(s)
    return _global_out(s)


def _personal_out(c: UserLlmConfig | None) -> PersonalConfigOut:
    if c is None:
        return PersonalConfigOut(
            base_url=None, model=None, api_key_masked=None, enabled=True
        )
    api_key = decrypt_secret(c.llm_api_key_enc) if c.llm_api_key_enc else None
    return PersonalConfigOut(
        base_url=c.llm_base_url,
        model=c.llm_model,
        api_key_masked=mask_secret(api_key),
        enabled=c.enabled,
    )


def get_personal(db: Session, operator: User) -> PersonalConfigOut:
    cfg = db.query(UserLlmConfig).filter(UserLlmConfig.user_id == operator.id).first()
    return _personal_out(cfg)


def update_personal(
    db: Session, operator: User, data: PersonalConfigUpdate
) -> PersonalConfigOut:
    cfg = db.query(UserLlmConfig).filter(UserLlmConfig.user_id == operator.id).first()
    if cfg is None:
        cfg = UserLlmConfig(user_id=operator.id)
        db.add(cfg)

    payload = data.model_dump(exclude_unset=True)
    if "api_key" in payload:
        key = payload.pop("api_key")
        cfg.llm_api_key_enc = encrypt_secret(key) if key else None
    if "base_url" in payload:
        cfg.llm_base_url = payload["base_url"] or None
    if "model" in payload:
        cfg.llm_model = payload["model"] or None
    if "enabled" in payload:
        cfg.enabled = payload["enabled"]

    db.commit()
    db.refresh(cfg)
    return _personal_out(cfg)


def test_connection(base_url: str, api_key: str | None, model: str | None) -> tuple[bool, str]:
    """探测 OpenAI 兼容端点连通性：先 GET /models，再回退 POST /chat/completions。"""
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{base}/models", headers=headers)
            if r.status_code == 200:
                return True, "连接成功"
    except httpx.HTTPError as exc:
        return False, f"无法连接：{exc}"

    try:
        with httpx.Client(timeout=10.0) as client:
            payload = {
                "model": model or "default",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            r = client.post(f"{base}/chat/completions", json=payload, headers=headers)
            if 200 <= r.status_code < 300:
                return True, "连接成功"
            return False, f"端点返回 HTTP {r.status_code}"
    except httpx.HTTPError as exc:
        return False, f"无法连接：{exc}"
