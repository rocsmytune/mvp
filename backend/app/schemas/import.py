"""手工物料导入的请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImportRowIn(BaseModel):
    """8 列原始行（键名与 importer.parse 内部一致）。"""

    bmc_ip: str | None = None
    machine_sn: str | None = None
    material_type: str | None = None
    sn: str | None = None
    material_code: str | None = None
    material_name: str | None = None
    remark: str | None = None
    holder: str | None = None


class UploadRequest(BaseModel):
    file_name: str | None = None
    rows: list[ImportRowIn]


class RowIssueOut(BaseModel):
    severity: str
    message: str


class FieldChangeOut(BaseModel):
    field: str
    old: str | None
    new: str | None


class PreviewRowOut(BaseModel):
    row_no: int
    action: str  # new / update / no_change / error
    material_type: str | None
    sn: str | None
    bmc_ip: str | None
    machine_sn: str | None
    asset_id: int | None
    asset_sn: str | None
    cabinet_name: str | None
    u_start: int | None
    u_end: int | None
    holder_name: str | None
    changes: list[FieldChangeOut]
    issues: list[RowIssueOut]


class SummaryOut(BaseModel):
    total: int
    new: int
    update: int
    no_change: int
    error: int
    warning: int


class UploadResponse(BaseModel):
    batch_id: int
    file_name: str | None
    summary: SummaryOut
    rows: list[PreviewRowOut]


class ConfirmRequest(BaseModel):
    batch_id: int


class ConfirmRowOut(BaseModel):
    row_no: int
    action: str
    result: str  # created / updated / skipped
    message: str | None = None


class CommitSummaryOut(BaseModel):
    total: int
    created: int
    updated: int
    skipped: int


class ConfirmResponse(BaseModel):
    batch_id: int
    status: str
    summary: CommitSummaryOut
    rows: list[ConfirmRowOut]


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str | None
    status: str
    operator_id: int | None
    created_at: datetime
    summary_json: dict | None = None


class BatchListOut(BaseModel):
    total: int
    items: list[BatchOut]
