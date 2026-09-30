from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.cabinet import (
    AssignResult,
    CabinetAssignOwner,
    CabinetCreate,
    CabinetListOut,
    CabinetOut,
    CabinetUpdate,
)
from app.services import cabinet as cabinet_service

router = APIRouter(prefix="/api/cabinets", tags=["cabinets"])


@router.post("", response_model=CabinetOut, status_code=201)
def create_cabinet(
    data: CabinetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return cabinet_service.create_cabinet(db, user, data)


@router.post("/assign-owner", response_model=AssignResult)
def assign_owner(
    data: CabinetAssignOwner,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    updated = cabinet_service.batch_assign_owner(db, user, data.cabinet_ids, data.owner_id)
    return AssignResult(updated=updated)


@router.get("", response_model=CabinetListOut)
def list_cabinets(
    room_id: int | None = None,
    owner_id: int | None = None,
    skip: int = 0,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = cabinet_service.list_cabinets(
        db, room_id=room_id, owner_id=owner_id, skip=skip, limit=limit
    )
    return CabinetListOut(total=total, items=items)


@router.get("/{cabinet_id}", response_model=CabinetOut)
def get_cabinet(
    cabinet_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return cabinet_service.get_cabinet(db, cabinet_id)


@router.patch("/{cabinet_id}", response_model=CabinetOut)
def update_cabinet(
    cabinet_id: int,
    data: CabinetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return cabinet_service.update_cabinet(db, user, cabinet_id, data)


@router.delete("/{cabinet_id}", status_code=204)
def delete_cabinet(
    cabinet_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cabinet_service.delete_cabinet(db, user, cabinet_id)
