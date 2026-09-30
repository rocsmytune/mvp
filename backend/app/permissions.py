"""权限判断唯一入口。所有写接口与敏感读接口必须经过此模块校验。

规则（PRD 第2节）：
- 总管理员 admin：全权。
- 柜主 cabinet_owner：仅能操作 owner 为自己的机柜及其下设备/部件。
- 普通成员 member：只读（写操作一律拒绝）。
"""

from fastapi import HTTPException, status

from app.models.cabinet import Cabinet
from app.models.user import User

ROLE_ADMIN = "admin"
ROLE_CABINET_OWNER = "cabinet_owner"
ROLE_MEMBER = "member"


def require_admin(user: User) -> None:
    """仅总管理员可执行。"""
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅总管理员可执行此操作"
        )


def ensure_can_manage_cabinet(user: User, cabinet: Cabinet | None) -> None:
    """校验能否管理某机柜及其下资产。

    cabinet 为 None 表示待整理池资产（无归属机柜），此时仅 admin 可操作。
    """
    if user.role == ROLE_ADMIN:
        return
    if (
        cabinet is not None
        and user.role == ROLE_CABINET_OWNER
        and cabinet.owner_id == user.id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该机柜及其资产"
    )
