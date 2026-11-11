from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.room_type import RoomTypeCreate, RoomTypeResponse, RoomTypeUpdate
from app.services import room_type_service as service


router = APIRouter(
    prefix="/api/properties/{property_id}/room-types",
    tags=["Room types"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.post("", response_model=RoomTypeResponse, status_code=status.HTTP_201_CREATED)
def create_room_type(property_id: int, data: RoomTypeCreate, db: Session = Depends(get_db),
                     user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return service.create_room_type(db, user, property_id, data)


@router.get("", response_model=list[RoomTypeResponse])
def list_room_types(property_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return service.list_room_types(db, user, property_id)


@router.get("/{room_type_id}", response_model=RoomTypeResponse)
def read_room_type(property_id: int, room_type_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return service.read_room_type(db, user, property_id, room_type_id)


@router.patch("/{room_type_id}", response_model=RoomTypeResponse)
def update_room_type(property_id: int, room_type_id: int, data: RoomTypeUpdate, db: Session = Depends(get_db),
                     user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return service.update_room_type(db, user, property_id, room_type_id, data)


@router.delete("/{room_type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room_type(property_id: int, room_type_id: int, db: Session = Depends(get_db),
                     user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    service.delete_room_type(db, user, property_id, room_type_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
