from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ComponentCreate(BaseModel):
    asset_id: int
    category: str
    sn: str | None = None
    model: str | None = None
    qty: int = 1
    sn_source: str = "manual"
    remark: str | None = None


class ComponentUpdate(BaseModel):
    category: str | None = None
    sn: str | None = None
    model: str | None = None
    qty: int | None = None
    sn_source: str | None = None
    remark: str | None = None


class ComponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: int
    category: str
    sn: str | None
    model: str | None
    qty: int
    sn_source: str
    remark: str | None
    updated_at: datetime


class ComponentListOut(BaseModel):
    total: int
    items: list[ComponentOut]
