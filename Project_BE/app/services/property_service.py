from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Contract, Property, PropertyManager, Room
from app.models.user import User
from app.schemas.boarding import ManagerAssign, PropertyCreate, PropertyUpdate, RoomCreate, RoomUpdate
from app.services.access_scope import assert_can_manage, assert_can_operate, get_property, get_room, property_of_room
from app.services.db_util import save


def create_property(db: Session, user: User, data: PropertyCreate) -> Property:
    prop = Property(
        owner_id=user.id, name=data.name, address=data.address,
        electricity_unit_price=data.electricity_unit_price,
        water_unit_price=data.water_unit_price,
        service_unit_price=data.service_unit_price,
    )
    db.add(prop)
    save(db, prop)
    return prop


def list_properties(db: Session, user: User) -> list[Property]:
    if user.role == Role.LANDLORD.value:
        stmt = select(Property).where(Property.owner_id == user.id)
    elif user.role == Role.MANAGER.value:
        stmt = (
            select(Property)
            .join(PropertyManager, PropertyManager.property_id == Property.id)
            .where(PropertyManager.user_id == user.id)
        )
    else:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện chức năng này.")
    return list(db.scalars(stmt.order_by(Property.id)))


def read_property(db: Session, user: User, property_id: int) -> Property:
    prop = get_property(db, property_id)
    assert_can_operate(db, user, prop)
    return prop


def update_property(db: Session, user: User, property_id: int, data: PropertyUpdate) -> Property:
    prop = get_property(db, property_id)
    assert_can_manage(user, prop)
    for field in ("name", "address", "electricity_unit_price", "water_unit_price", "service_unit_price"):
        value = getattr(data, field)
        if value is not None:
            setattr(prop, field, value)
    save(db, prop)
    return prop


def delete_property(db: Session, user: User, property_id: int) -> None:
    prop = get_property(db, property_id)
    assert_can_manage(user, prop)
    has_room = db.scalar(select(Room.id).where(Room.property_id == prop.id))
    if has_room is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa khu trọ còn phòng.")
    db.delete(prop)
    save(db)


def assign_manager(db: Session, user: User, property_id: int, data: ManagerAssign) -> PropertyManager:
    prop = get_property(db, property_id)
    assert_can_manage(user, prop)
    manager = db.get(User, data.user_id)
    if manager is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản người quản lý.")
    if manager.role != Role.MANAGER.value:
        raise HTTPException(status_code=422, detail="Chỉ gán được tài khoản có vai trò người quản lý.")
    existing = db.get(PropertyManager, (prop.id, manager.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Người quản lý đã được gán cho khu trọ này.")
    link = PropertyManager(property_id=prop.id, user_id=manager.id)
    db.add(link)
    save(db, link)
    return link


def create_room(db: Session, user: User, property_id: int, data: RoomCreate) -> Room:
    prop = get_property(db, property_id)
    assert_can_operate(db, user, prop)
    taken = db.scalar(select(Room).where(Room.property_id == prop.id, Room.room_number == data.room_number))
    if taken is not None:
        raise HTTPException(status_code=409, detail="Số phòng đã tồn tại trong khu trọ.")
    room = Room(property_id=prop.id, room_number=data.room_number, base_rent=data.base_rent, status="available")
    db.add(room)
    save(db, room)
    return room


def list_rooms(db: Session, user: User, property_id: int) -> list[Room]:
    prop = get_property(db, property_id)
    assert_can_operate(db, user, prop)
    return list(db.scalars(select(Room).where(Room.property_id == prop.id).order_by(Room.id)))


def update_room(db: Session, user: User, room_id: int, data: RoomUpdate) -> Room:
    room = get_room(db, room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if data.base_rent is not None:
        room.base_rent = data.base_rent
    if data.status is not None:
        active = db.scalar(select(Contract.id).where(Contract.room_id == room.id, Contract.status == "active"))
        if data.status == "available" and active is not None:
            raise HTTPException(status_code=409, detail="Không thể chuyển phòng đang có hợp đồng hoạt động sang Trống.")
        room.status = data.status
    save(db, room)
    return room
