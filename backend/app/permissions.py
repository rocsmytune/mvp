"""权限判断唯一入口。所有写接口与敏感读接口必须经过此模块校验。

角色（PRD 第2节）：
- 系统管理员 system_admin：全权（含用户管理）。
- 物料管理员 material_admin：物料/机柜/导入/导出，不含用户管理。
- 柜主 cabinet_owner：仅能操作 owner 为自己的机柜及其下设备/部件。
- 普通成员 member：只读（写操作一律拒绝）。
"""

from fastapi import HTTPException, status

from app.models.cabinet import Cabinet
from app.models.user import User

ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_MATERIAL_ADMIN = "material_admin"
ROLE_CABINET_OWNER = "cabinet_owner"
ROLE_MEMBER = "member"

# 业务管理员（物料/机柜/导入/导出）；系统管理员同时具备业务管理员权限。
ADMIN_ROLES = (ROLE_SYSTEM_ADMIN, ROLE_MATERIAL_ADMIN)


def _is_admin(user: User) -> bool:
    return user.role in ADMIN_ROLES


def require_admin(user: User) -> None:
    """业务管理员（系统管理员/物料管理员）可执行。"""
    if not _is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可执行此操作"
        )


def require_system_admin(user: User) -> None:
    """仅系统管理员可执行（用户管理）。"""
    if user.role != ROLE_SYSTEM_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="仅系统管理员可执行此操作"
        )


def can_manage_cabinet(user: User, cabinet: Cabinet | None) -> bool:
    """判断能否管理某机柜及其下资产（只读谓词，供导入等按行判定复用）。

    cabinet 为 None 表示待整理池资产（无归属机柜），此时仅管理员可操作。
    """
    if _is_admin(user):
        return True
    if (
        cabinet is not None
        and user.role == ROLE_CABINET_OWNER
        and cabinet.owner_id == user.id
    ):
        return True
    return False


def ensure_can_manage_cabinet(user: User, cabinet: Cabinet | None) -> None:
    """校验能否管理某机柜及其下资产，无权限则抛 403。"""
    if not can_manage_cabinet(user, cabinet):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该机柜及其资产"
        )
