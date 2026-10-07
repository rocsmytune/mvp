import importlib

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User

# 模块文件名是 Python 关键字「import」，需经 importlib 导入
import_schemas = importlib.import_module("app.schemas.import")
import_service = importlib.import_module("app.services.import")

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/upload", response_model=import_schemas.UploadResponse)
def upload(
    data: import_schemas.UploadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = [r.model_dump() for r in data.rows]
    return import_service.preview(db, user, data.file_name, rows)


@router.post("/confirm", response_model=import_schemas.ConfirmResponse)
def confirm(
    data: import_schemas.ConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return import_service.commit(db, user, data.batch_id)


@router.get("/batches", response_model=import_schemas.BatchListOut)
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = import_service.list_batches(db, user)
    return import_schemas.BatchListOut(total=total, items=items)
