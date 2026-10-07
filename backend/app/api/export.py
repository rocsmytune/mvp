from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.permissions import require_admin
from app.schemas.export import ExportSnapshotOut
from app.services import export as export_service

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/snapshot", response_model=ExportSnapshotOut)
def get_snapshot(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导出全量备份快照（仅总管理员）。"""
    require_admin(user)
    return export_service.get_snapshot(db)
