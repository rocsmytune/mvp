from pydantic import BaseModel, ConfigDict


class CabinetCreate(BaseModel):
    room_id: int
    name: str
    row_no: str | None = None
    col_no: int | None = None
    total_u: int = 45
    owner_id: int | None = None


class CabinetUpdate(BaseModel):
    room_id: int | None = None
    name: str | None = None
    row_no: str | None = None
    col_no: int | None = None
    total_u: int | None = None
    owner_id: int | None = None


class CabinetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    row_no: str | None
    col_no: int | None
    total_u: int
    owner_id: int | None
    owner_name: str | None
    room_code: str | None


class CabinetListOut(BaseModel):
    total: int
    items: list[CabinetOut]


class CabinetAssignOwner(BaseModel):
    cabinet_ids: list[int]
    owner_id: int | None = None


class AssignResult(BaseModel):
    updated: int
