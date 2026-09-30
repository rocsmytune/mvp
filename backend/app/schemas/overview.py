from pydantic import BaseModel

from app.schemas.room import RoomOut


class OverviewCabinet(BaseModel):
    id: int
    room_id: int
    room_code: str | None
    name: str
    owner_id: int | None
    owner_name: str | None
    total_u: int
    device_count: int
    used_u: int


class OverviewOut(BaseModel):
    placed_count: int
    pool_count: int
    rooms: list[RoomOut]
    cabinets: list[OverviewCabinet]
