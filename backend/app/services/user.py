"""用户管理业务逻辑。仅系统管理员，统一写 ChangeLog。"""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.permissions import require_admin, require_system_admin
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate, UserUpdate
from app.services import changelog


def _get(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _check_employee_no_unique(
    db: Session, employee_no: str, exclude_id: int | None = None
) -> None:
    query = db.query(User).filter(User.employee_no == employee_no)
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(status_code=409, detail=f"工号 {employee_no} 已存在")


def list_users(
    db: Session,
    operator: User,
    *,
    q: str | None = None,
    role: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[User], int]:
    require_system_admin(operator)
    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(User.employee_no.ilike(like), User.name.ilike(like))
        )
    if role:
        query = query.filter(User.role == role)
    total = query.count()
    items = query.order_by(User.id).offset(skip).limit(limit).all()
    return items, total


def list_cabinet_owners(db: Session, operator: User) -> list[User]:
    """机柜指派柜主下拉：返回启用中的 cabinet_owner 用户（两个管理员角色可看）。"""
    require_admin(operator)
    return (
        db.query(User)
        .filter(User.role == "cabinet_owner", User.active.is_(True))
        .order_by(User.employee_no)
        .all()
    )


def register_user(db: Session, data: RegisterRequest) -> User:
    """自助注册：仅开放 member / cabinet_owner，注册后 active 直接可用。

    ChangeLog 的 operator 记为注册者本人（此时用户已 flush、拿到 id）。
    """
    _check_employee_no_unique(db, data.employee_no)

    user = User(
        employee_no=data.employee_no,
        name=data.name,
        role=data.role,
        auth_source="local",
        password_hash=hash_password(data.password),
        active=True,
        dept_id=settings.dept_id,
    )
    db.add(user)
    db.flush()
    changelog.log(
        db, operator=user, target_type="user", target_id=user.id,
        cabinet_id=None, action="create",
    )
    db.commit()
    db.refresh(user)
    return user


def create_user(db: Session, operator: User, data: UserCreate) -> User:
    require_system_admin(operator)
    _check_employee_no_unique(db, data.employee_no)

    user = User(
        employee_no=data.employee_no,
        name=data.name,
        role=data.role,
        auth_source="local",
        password_hash=hash_password(data.password),
        dept_id=settings.dept_id,
    )
    db.add(user)
    db.flush()
    changelog.log(
        db, operator=operator, target_type="user", target_id=user.id,
        cabinet_id=None, action="create",
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session, operator: User, user_id: int, data: UserUpdate
) -> User:
    require_system_admin(operator)
    target = _get(db, user_id)
    changes = data.model_dump(exclude_unset=True)

    # 不能禁用或降级自己，避免把自己锁在用户管理之外。
    if operator.id == target.id and (
        "role" in changes or changes.get("active") is False
    ):
        raise HTTPException(status_code=403, detail="不能修改自己的角色或禁用自己")

    for field, value in changes.items():
        if field == "password":
            # 密码只重置，ChangeLog 不记录任何值。
            target.password_hash = hash_password(value)
            changelog.log(
                db, operator=operator, target_type="user", target_id=target.id,
                cabinet_id=None, action="update", field=field,
            )
            continue
        old = getattr(target, field)
        if old == value:
            continue
        setattr(target, field, value)
        changelog.log(
            db, operator=operator, target_type="user", target_id=target.id,
            cabinet_id=None, action="update", field=field,
            old_value=old, new_value=value,
        )
    db.commit()
    db.refresh(target)
    return target
