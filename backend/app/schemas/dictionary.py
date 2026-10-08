from pydantic import BaseModel, ConfigDict, Field


class DictionaryCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    code: str = Field(min_length=1, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    sort_no: int = 0


class DictionaryUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=32)
    label: str | None = Field(default=None, min_length=1, max_length=64)
    sort_no: int | None = None


class DictionaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    code: str
    label: str
    sort_no: int
    usage_count: int = 0


class DictionaryListOut(BaseModel):
    total: int
    items: list[DictionaryOut]


class DictionaryUsageOut(BaseModel):
    target_type: str  # asset / component
    sn: str | None  # 自身 SN
    asset_sn: str | None  # 父资产 SN（仅 component）
    name: str | None  # model
    cabinet_name: str | None
    u_start: int | None
    u_end: int | None
