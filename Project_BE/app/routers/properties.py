from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import (
    ManagerAssign,
    ManagerAssignmentResponse,
    PropertyCreate,
    PropertyResponse,
    PropertyUpdate,
    RoomCreate,
    RoomDetailResponse,
    RoomListResponse,
    RoomResponse,
    RoomUpdate,
)
from app.services import property_service

router = APIRouter(
    prefix="/api/properties",
    tags=["Properties"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)
room_router = APIRouter(
    prefix="/api/rooms",
    tags=["Rooms"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("", response_model=list[PropertyResponse])
def read_properties(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.list_properties(db, user)


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    data: PropertyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_MANAGE)),
):
    return property_service.create_property(db, user, data)


@router.get("/{property_id}", response_model=PropertyResponse)
def read_property(
    property_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.read_property(db, user, property_id)


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: int,
    data: PropertyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_MANAGE)),
):
    return property_service.update_property(db, user, property_id, data)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_MANAGE)),
):
    property_service.delete_property(db, user, property_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{property_id}/managers", response_model=ManagerAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_manager(
    property_id: int,
    data: ManagerAssign,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_MANAGE)),
):
    link = property_service.assign_manager(db, user, property_id, data)
    return ManagerAssignmentResponse(property_id=link.property_id, user_id=link.user_id)


@router.get("/{property_id}/rooms", response_model=list[RoomResponse])
def read_rooms(
    property_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.list_rooms(db, user, property_id)


@router.post("/{property_id}/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    property_id: int,
    data: RoomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.create_room(db, user, property_id, data)


@room_router.put("/{room_id}", response_model=RoomResponse)
def update_room(
    room_id: int,
    data: RoomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.update_room(db, user, room_id, data)


@room_router.get("", response_model=RoomListResponse)
def read_all_rooms(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    search: str | None = Query(default=None, max_length=20),
    property_id: int | None = Query(default=None, gt=0),
    room_status: str | None = Query(default=None, alias="status", pattern="^(available|occupied|maintenance)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.list_all_rooms(db, user, page, page_size, search, property_id, room_status)


@room_router.get("/{room_id}", response_model=RoomDetailResponse)
def read_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return property_service.read_room(db, user, room_id)


@room_router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    property_service.delete_room(db, user, room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
