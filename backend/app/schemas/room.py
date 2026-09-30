from pydantic import BaseModel, ConfigDict


class RoomCreate(BaseModel):
    city: str | None = None
    code: str
    zone: str | None = None
    remark: str | None = None


class RoomUpdate(BaseModel):
    city: str | None = None
    code: str | None = None
    zone: str | None = None
    remark: str | None = None


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str | None
    code: str
    zone: str | None
    remark: str | None


class RoomListOut(BaseModel):
    total: int
    items: list[RoomOut]
