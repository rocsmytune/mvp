from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AssetCreate(BaseModel):
    type: Literal["server", "switch"]
    cabinet_id: int | None = None
    u_start: int | None = None
    u_end: int | None = None
    sn: str | None = None
    asset_tag: str | None = None
    model: str | None = None
    cpu_model: str | None = None
    ip_inband: str | None = None
    bmc_ip: str | None = None
    status: str = "in_use"
    remark: str | None = None


class AssetUpdate(BaseModel):
    type: Literal["server", "switch"] | None = None
    cabinet_id: int | None = None
    u_start: int | None = None
    u_end: int | None = None
    sn: str | None = None
    asset_tag: str | None = None
    model: str | None = None
    cpu_model: str | None = None
    ip_inband: str | None = None
    bmc_ip: str | None = None
    status: str | None = None
    remark: str | None = None


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    cabinet_id: int | None
    u_start: int | None
    u_end: int | None
    sn: str | None
    asset_tag: str | None
    model: str | None
    cpu_model: str | None
    ip_inband: str | None
    bmc_ip: str | None
    status: str
    in_pool: bool
    location_raw: str | None
    pool_reason: str | None
    field_source: dict
    remark: str | None
    created_at: datetime
    updated_at: datetime


class AssetListOut(BaseModel):
    total: int
    items: list[AssetOut]
