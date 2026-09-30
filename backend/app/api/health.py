from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """健康检查：同时验证后端进程与数据库连通。"""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
