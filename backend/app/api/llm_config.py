from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.llm_config import (
    GlobalConfigOut,
    GlobalConfigUpdate,
    PersonalConfigOut,
    PersonalConfigUpdate,
    TestConnRequest,
    TestConnResponse,
)
from app.services import llm_config as service

router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])


@router.get("/global", response_model=GlobalConfigOut)
def get_global(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """全局默认配置（所有登录用户可读，api_key 仅打码回显）。"""
    return service.get_global(db)


@router.put("/global", response_model=GlobalConfigOut)
def update_global(
    data: GlobalConfigUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    """修改全局默认配置（仅 system_admin）。"""
    return service.update_global(db, operator, data)


@router.get("/me", response_model=PersonalConfigOut)
def get_personal(
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    """我的个人配置（覆盖全局默认）。"""
    return service.get_personal(db, operator)


@router.put("/me", response_model=PersonalConfigOut)
def update_personal(
    data: PersonalConfigUpdate,
    db: Session = Depends(get_db),
    operator: User = Depends(get_current_user),
):
    """修改我的个人配置（登录用户本人）。"""
    return service.update_personal(db, operator, data)


@router.post("/test", response_model=TestConnResponse)
def test_connection(
    data: TestConnRequest,
    user: User = Depends(get_current_user),
):
    """用临时值测试端点连通性（不落库）。"""
    ok, message = service.test_connection(data.base_url, data.api_key, data.model)
    return TestConnResponse(ok=ok, message=message)
