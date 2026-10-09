from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.local import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.component import ComponentCreate, ComponentListOut, ComponentOut, ComponentUpdate
from app.schemas.facet import FacetValue
from app.services import component as component_service

router = APIRouter(prefix="/api/components", tags=["components"])


@router.post("", response_model=ComponentOut, status_code=201)
def create_component(
    data: ComponentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return component_service.create_component(db, user, data)


@router.get("", response_model=ComponentListOut)
def list_components(
    asset_id: int | None = None,
    category: str | None = None,
    q: str | None = None,
    categories: list[str] | None = Query(None),
    sns: list[str] | None = Query(None),
    material_codes: list[str] | None = Query(None),
    holder_names: list[str] | None = Query(None),
    room_codes: list[str] | None = Query(None),
    cabinet_names: list[str] | None = Query(None),
    skip: int = 0,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = component_service.list_components(
        db,
        asset_id=asset_id,
        category=category,
        q=q,
        categories=categories,
        sns=sns,
        material_codes=material_codes,
        holder_names=holder_names,
        room_codes=room_codes,
        cabinet_names=cabinet_names,
        skip=skip,
        limit=limit,
    )
    return ComponentListOut(total=total, items=items)


@router.get("/facets", response_model=dict[str, list[FacetValue]])
def list_component_facets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return component_service.list_component_facets(db)


@router.patch("/{component_id}", response_model=ComponentOut)
def update_component(
    component_id: int,
    data: ComponentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return component_service.update_component(db, user, component_id, data)


@router.delete("/{component_id}", status_code=204)
def delete_component(
    component_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    component_service.delete_component(db, user, component_id)
