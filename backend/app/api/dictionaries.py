from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.dictionary import (
    DictionaryCreate,
    DictionaryListOut,
    DictionaryOut,
    DictionaryUpdate,
    DictionaryUsageOut,
)
from app.services import dictionary as dictionary_service

router = APIRouter(prefix="/api/dictionaries", tags=["dictionaries"])


@router.get("", response_model=DictionaryListOut)
def list_dictionaries(
    kind: str | None = None,
    skip: int = 0,
    limit: int = Query(500, le=500),
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),  # 读开放，仅需登录
):
    items, total = dictionary_service.list_dictionaries(
        db, kind=kind, skip=skip, limit=limit
    )
    return DictionaryListOut(total=total, items=items)


@router.post("", response_model=DictionaryOut, status_code=201)
def create_dictionary(
    data: DictionaryCreate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    return dictionary_service.create_dictionary(db, operator, data)


@router.patch("/{dict_id}", response_model=DictionaryOut)
def update_dictionary(
    dict_id: int,
    data: DictionaryUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    return dictionary_service.update_dictionary(db, operator, dict_id, data)


@router.delete("/{dict_id}", status_code=204)
def delete_dictionary(
    dict_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    dictionary_service.delete_dictionary(db, operator, dict_id)


@router.get("/{dict_id}/usage", response_model=list[DictionaryUsageOut])
def get_usage(
    dict_id: int,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),  # 读开放，仅需登录
):
    return dictionary_service.get_usage(db, dict_id)
