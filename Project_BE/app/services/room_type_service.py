from functools import wraps

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.room_type import RoomType, RoomTypeAssignment
from app.models.user import User
from app.schemas.room_type import RoomTypeCreate, RoomTypeUpdate
from app.services.access_scope import assert_can_operate, get_property
from app.services.db_util import save


def database_errors(function):
    @wraps(function)
    def wrapped(db: Session, *args, **kwargs):
        try:
            return function(db, *args, **kwargs)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "Dữ liệu vi phạm ràng buộc hoặc còn liên kết.") from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(503, "Không thể truy cập database. Vui lòng thử lại sau.") from exc
    return wrapped


def authorized_property(db: Session, user: User, property_id: int):
    # Dùng đúng phạm vi chủ trọ/quản lý đã được hệ thống phân công.
    prop = get_property(db, property_id)
    assert_can_operate(db, user, prop)
    return prop


def get_room_type(db: Session, user: User, property_id: int, room_type_id: int) -> RoomType:
    authorized_property(db, user, property_id)
    room_type = db.scalar(select(RoomType).where(
        RoomType.id == room_type_id, RoomType.property_id == property_id,
    ))
    if room_type is None:
        raise HTTPException(404, "Không tìm thấy loại phòng trong khu trọ.")
    return room_type


@database_errors
def create_room_type(db: Session, user: User, property_id: int, data: RoomTypeCreate) -> RoomType:
    authorized_property(db, user, property_id)
    room_type = RoomType(property_id=property_id, **data.model_dump())
    db.add(room_type)
    save(db, room_type)
    return room_type


@database_errors
def list_room_types(db: Session, user: User, property_id: int) -> list[RoomType]:
    authorized_property(db, user, property_id)
    return list(db.scalars(select(RoomType).where(RoomType.property_id == property_id).order_by(RoomType.id)))


@database_errors
def read_room_type(db: Session, user: User, property_id: int, room_type_id: int) -> RoomType:
    return get_room_type(db, user, property_id, room_type_id)


@database_errors
def update_room_type(db: Session, user: User, property_id: int, room_type_id: int, data: RoomTypeUpdate) -> RoomType:
    room_type = get_room_type(db, user, property_id, room_type_id)
    # Chỉ đổi giá niêm yết; không ghi vào phòng hoặc hợp đồng hiện có.
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room_type, field, value)
    save(db, room_type)
    return room_type


@database_errors
def delete_room_type(db: Session, user: User, property_id: int, room_type_id: int) -> None:
    room_type = get_room_type(db, user, property_id, room_type_id)
    # Chặn xóa khi đang được sử dụng; FK RESTRICT bảo vệ cả khi có thao tác đồng thời.
    used = db.scalar(select(RoomTypeAssignment.room_id).where(RoomTypeAssignment.room_type_id == room_type.id))
    if used is not None:
        raise HTTPException(409, "Không thể xóa loại phòng đang được phòng sử dụng.")
    db.delete(room_type)
    save(db)
