from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ComponentCreate(BaseModel):
    asset_id: int
    category: str
    sn: str | None = None
    model: str | None = None
    name: str | None = None
    material_code: str | None = None
    sn_source: str = "manual"
    remark: str | None = None
    holder_name: str | None = None


class ComponentUpdate(BaseModel):
    category: str | None = None
    sn: str | None = None
    model: str | None = None
    name: str | None = None
    material_code: str | None = None
    sn_source: str | None = None
    remark: str | None = None
    holder_name: str | None = None


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    category: str
    sn: str | None
    model: str | None
    name: str | None
    material_code: str | None
    sn_source: str
    remark: str | None
    holder_id: int | None
    holder_name: str | None
    updated_at: datetime
    # 列表页定位上下文（仅 list_components 联表填充，非表字段；其余接口为 None）
    asset_sn: str | None = None
    asset_model: str | None = None
    cabinet_id: int | None = None
    cabinet_name: str | None = None
    room_code: str | None = None


class ComponentListOut(BaseModel):
    total: int
    items: list[ComponentOut]
