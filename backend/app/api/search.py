from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.search import SearchResultOut
from app.services import search as search_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("", response_model=list[SearchResultOut])
def global_search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全局搜索（只读，三种角色均可）：整机SN / 部件SN / 带内IP / 带外IP / 资产编号。"""
    return search_service.search(db, q, limit)
