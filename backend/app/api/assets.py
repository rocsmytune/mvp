from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetListOut, AssetOut, AssetUpdate
from app.schemas.changelog import ChangeLogOut
from app.schemas.facet import FacetValue
from app.services import asset as asset_service
from app.services import changelog

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(
    data: AssetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return asset_service.create_asset(db, user, data)


@router.get("", response_model=AssetListOut)
def list_assets(
    cabinet_id: int | None = None,
    in_pool: bool | None = None,
    type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    types: list[str] | None = Query(None),
    statuses: list[str] | None = Query(None),
    models: list[str] | None = Query(None),
    sns: list[str] | None = Query(None),
    ip_inbands: list[str] | None = Query(None),
    bmc_ips: list[str] | None = Query(None),
    room_codes: list[str] | None = Query(None),
    cabinet_names: list[str] | None = Query(None),
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = asset_service.list_assets(
        db,
        cabinet_id=cabinet_id,
        in_pool=in_pool,
        asset_type=type,
        status=status,
        q=q,
        types=types,
        statuses=statuses,
        models=models,
        sns=sns,
        ip_inbands=ip_inbands,
        bmc_ips=bmc_ips,
        room_codes=room_codes,
        cabinet_names=cabinet_names,
        skip=skip,
        limit=limit,
    )
    return AssetListOut(total=total, items=items)


@router.get("/facets", response_model=dict[str, list[FacetValue]])
def list_asset_facets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return asset_service.list_asset_facets(db)


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return asset_service.get_asset(db, asset_id)


@router.get("/{asset_id}/changelogs", response_model=list[ChangeLogOut])
def list_asset_changelogs(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 校验资产存在（不存在/已删除则 404），再返回其变更日志。
    asset_service.get_asset(db, asset_id)
    return changelog.list_for_asset(db, asset_id)


@router.patch("/{asset_id}", response_model=AssetOut)
def update_asset(
    asset_id: int,
    data: AssetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return asset_service.update_asset(db, user, asset_id, data)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset_service.delete_asset(db, user, asset_id)
