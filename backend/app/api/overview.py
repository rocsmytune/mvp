from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.overview import OverviewOut
from app.services import overview as overview_service

router = APIRouter(prefix="/api/overview", tags=["overview"])


@router.get("", response_model=OverviewOut)
def get_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return overview_service.get_overview(db)
