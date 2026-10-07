from pydantic import BaseModel


class SearchResultOut(BaseModel):
    """全局搜索结果（资产或部件命中），带「机房-机柜-U位-柜主」定位信息。"""

    kind: str  # asset / component
    matched_field: str  # sn / asset_tag / ip_inband / bmc_ip / component_sn
    # 定位信息（待整理池设备为 None）
    room_code: str | None
    cabinet_id: int | None
    cabinet_name: str | None
    u_start: int | None
    u_end: int | None
    owner_name: str | None
    # 资产信息（kind=component 时为父整机）
    asset_id: int
    asset_type: str
    asset_sn: str | None
    asset_tag: str | None
    model: str | None
    ip_inband: str | None
    bmc_ip: str | None
    status: str
    in_pool: bool
    # 部件信息（kind=component 时有效）
    component_id: int | None
    component_category: str | None
    component_sn: str | None
    component_name: str | None
