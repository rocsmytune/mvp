"""AI 助手 LLM 配置的请求/响应模型。"""

from pydantic import BaseModel, Field


class GlobalConfigUpdate(BaseModel):
    """全局默认配置（仅 system_admin 可 PUT）。api_key 省略=不改，传空串=清除。"""

    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    model: str | None = Field(None, max_length=128)
    daily_token_quota: int | None = Field(None, ge=0, le=10_000_000)


class GlobalConfigOut(BaseModel):
    base_url: str | None
    model: str | None
    api_key_masked: str | None
    daily_token_quota: int
    configured: bool  # base_url 与 model 均已配置（api_key 可选）


class PersonalConfigUpdate(BaseModel):
    """个人配置（登录用户本人 PUT）。"""

    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    model: str | None = Field(None, max_length=128)
    enabled: bool | None = None


class PersonalConfigOut(BaseModel):
    base_url: str | None
    model: str | None
    api_key_masked: str | None
    enabled: bool


class TestConnRequest(BaseModel):
    """测试连通：用传入的临时值调 LLM 端点，不落库。"""

    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(None, max_length=500)
    model: str | None = Field(None, max_length=128)


class TestConnResponse(BaseModel):
    ok: bool
    message: str
