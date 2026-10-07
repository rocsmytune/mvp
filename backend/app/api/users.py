from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import UserAdminOut, UserCreate, UserListOut, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=UserListOut)
def list_users(
    q: str | None = None,
    role: str | None = None,
    skip: int = 0,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    items, total = user_service.list_users(
        db, operator, q=q, role=role, skip=skip, limit=limit
    )
    return UserListOut(total=total, items=items)


@router.post("", response_model=UserAdminOut, status_code=201)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    return user_service.create_user(db, operator, data)


@router.patch("/{user_id}", response_model=UserAdminOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    return user_service.update_user(db, operator, user_id, data)
