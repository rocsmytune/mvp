from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.room import RoomCreate, RoomListOut, RoomOut, RoomUpdate
from app.services import room as room_service

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.post("", response_model=RoomOut, status_code=201)
def create_room(
    data: RoomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return room_service.create_room(db, user, data)


@router.get("", response_model=RoomListOut)
def list_rooms(
    q: str | None = None,
    skip: int = 0,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = room_service.list_rooms(db, q=q, skip=skip, limit=limit)
    return RoomListOut(total=total, items=items)


@router.get("/{room_id}", response_model=RoomOut)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return room_service.get_room(db, room_id)


@router.patch("/{room_id}", response_model=RoomOut)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return room_service.update_room(db, user, room_id, data)


@router.delete("/{room_id}", status_code=204)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room_service.delete_room(db, user, room_id)
