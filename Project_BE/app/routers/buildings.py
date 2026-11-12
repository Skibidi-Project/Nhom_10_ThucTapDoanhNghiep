from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.building import BuildingCreate, BuildingResponse, BuildingUpdate, FloorRename, FloorResponse
from app.services import building_service

property_router = APIRouter(
    prefix="/api/properties",
    tags=["Buildings & Floors"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)
router = APIRouter(
    prefix="/api/buildings",
    tags=["Buildings & Floors"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@property_router.get("/{property_id}/buildings", response_model=list[BuildingResponse])
def list_buildings(
    property_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return building_service.list_buildings(db, user, property_id)


@property_router.post("/{property_id}/buildings", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(
    property_id: int,
    data: BuildingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return building_service.create_building(db, user, property_id, data)


@router.get("/{building_id}", response_model=BuildingResponse)
def read_building(
    building_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return building_service.read_building(db, user, building_id)


@router.put("/{building_id}", response_model=BuildingResponse)
def update_building(
    building_id: int,
    data: BuildingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return building_service.update_building(db, user, building_id, data)


@router.put("/{building_id}/floors/{floor_id}", response_model=FloorResponse)
def rename_floor(
    building_id: int,
    floor_id: int,
    data: FloorRename,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return building_service.rename_floor(db, user, building_id, floor_id, data)


@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_building(
    building_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    building_service.delete_building(db, user, building_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
