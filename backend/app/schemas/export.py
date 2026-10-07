"""导出备份快照：机柜 / 资产 / 部件三层扁平化，全部用业务键（非数据库 id）。"""

from pydantic import BaseModel


class ExportCabinet(BaseModel):
    room_code: str | None
    name: str
    total_u: int
    owner_employee_no: str | None
    owner_name: str | None


class ExportAsset(BaseModel):
    room_code: str | None
    cabinet_name: str | None
    type: str  # 整机 / 交换机（已映射为中文，与导入物料类型一致）
    u_start: int | None
    u_end: int | None
    sn: str | None
    asset_tag: str | None
    model: str | None
    cpu_model: str | None
    ip_inband: str | None
    bmc_ip: str | None
    status: str
    holder_employee_no: str | None
    holder_name: str | None
    remark: str | None


class ExportComponent(BaseModel):
    # 8 列对齐手工物料导入，可直接重新导入。
    bmc_ip: str | None
    machine_sn: str | None
    material_type: str
    sn: str | None
    material_code: str | None
    material_name: str | None
    remark: str | None
    holder: str | None  # 「工号 姓名」；未匹配时为原文


class ExportSnapshotOut(BaseModel):
    cabinets: list[ExportCabinet]
    assets: list[ExportAsset]
    components: list[ExportComponent]
