from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["system_admin", "material_admin", "cabinet_owner", "member"]


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_no: str
    name: str
    role: str
    active: bool
    auth_source: str
    created_at: datetime


class UserCreate(BaseModel):
    employee_no: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    role: Role
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    password: str | None = Field(default=None, min_length=1, max_length=128)
    active: bool | None = None


class UserListOut(BaseModel):
    total: int
    items: list[UserAdminOut]


class OwnerOptionOut(BaseModel):
    """机柜指派柜主下拉：启用中的 cabinet_owner 用户（两个管理员角色可看）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_no: str
    name: str
