from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Contract, Property, PropertyManager, Room, TenantProfile, UtilityReading
from app.models.building import Building
from app.models.user import User
from app.schemas.boarding import (
    ManagerAssign,
    PropertyCreate,
    PropertyUpdate,
    RoomCreate,
    RoomDetailResponse,
    RoomListItem,
    RoomListResponse,
    RoomUpdate,
)
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
    has_building = db.scalar(select(Building.id).where(Building.property_id == prop.id))
    if has_building is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa khu trọ còn tòa nhà.")
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
    room = Room(
        property_id=prop.id,
        room_number=data.room_number,
        area_sqm=data.area_sqm,
        base_rent=data.base_rent,
        status="available",
    )
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
    if data.room_number is not None:
        taken = db.scalar(
            select(Room.id).where(
                Room.property_id == room.property_id,
                Room.room_number == data.room_number,
                Room.id != room.id,
            )
        )
        if taken is not None:
            raise HTTPException(status_code=409, detail="Số phòng đã tồn tại trong khu trọ.")
        room.room_number = data.room_number
    if data.area_sqm is not None:
        room.area_sqm = data.area_sqm
    if data.base_rent is not None:
        room.base_rent = data.base_rent
    if data.status is not None:
        active = db.scalar(select(Contract.id).where(Contract.room_id == room.id, Contract.status == "active"))
        if active is not None:
            raise HTTPException(status_code=409, detail="Không thể đổi trạng thái phòng đang có hợp đồng hoạt động.")
        room.status = data.status
    save(db, room)
    return room


def list_all_rooms(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    search: str | None,
    property_id: int | None,
    room_status: str | None,
) -> RoomListResponse:
    stmt = select(Room, Property.name).join(Property, Property.id == Room.property_id)
    if user.role == Role.LANDLORD.value:
        stmt = stmt.where(Property.owner_id == user.id)
    elif user.role == Role.MANAGER.value:
        stmt = stmt.join(PropertyManager, PropertyManager.property_id == Property.id).where(
            PropertyManager.user_id == user.id
        )

    if property_id is not None:
        prop = get_property(db, property_id)
        assert_can_operate(db, user, prop)
        stmt = stmt.where(Room.property_id == property_id)
    if search:
        escaped_search = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = stmt.where(Room.room_number.like(f"%{escaped_search}%", escape="\\"))
    if room_status is not None:
        stmt = stmt.where(Room.status == room_status)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(Room.property_id, Room.room_number, Room.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        RoomListItem(
            id=room.id,
            property_id=room.property_id,
            property_name=name,
            room_number=room.room_number,
            area_sqm=room.area_sqm,
            base_rent=room.base_rent,
            status=room.status,
        )
        for room, name in rows
    ]
    return RoomListResponse(items=items, total=total, page=page, page_size=page_size)


def read_room(db: Session, user: User, room_id: int) -> RoomDetailResponse:
    room = get_room(db, room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    row = db.execute(
        select(Contract, TenantProfile.full_name, Property.name)
        .select_from(Room)
        .join(Property, Property.id == Room.property_id)
        .outerjoin(Contract, and_(Contract.room_id == Room.id, Contract.status == "active"))
        .outerjoin(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(Room.id == room.id)
        .order_by(Contract.id)
    ).first()
    contract, tenant_name, property_name = row
    active_contract = None
    if contract is not None:
        active_contract = {
            "id": contract.id,
            "tenant": tenant_name,
            "start_date": contract.start_date,
            "end_date": contract.end_date,
            "monthly_rent": contract.monthly_rent,
        }
    return RoomDetailResponse(
        id=room.id,
        property_id=room.property_id,
        property_name=property_name,
        room_number=room.room_number,
        area_sqm=room.area_sqm,
        base_rent=room.base_rent,
        status=room.status,
        active_contract=active_contract,
    )


def delete_room(db: Session, user: User, room_id: int) -> None:
    room = get_room(db, room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    active = db.scalar(
        select(Contract.id).where(Contract.room_id == room.id, Contract.status == "active")
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa phòng đang có hợp đồng hoạt động.")
    has_contract = db.scalar(select(Contract.id).where(Contract.room_id == room.id))
    has_reading = db.scalar(select(UtilityReading.id).where(UtilityReading.room_id == room.id))
    if has_contract is not None or has_reading is not None:
        raise HTTPException(
            status_code=409,
            detail="Phòng đã có lịch sử hợp đồng/chỉ số, không thể xóa. Hãy chuyển sang Bảo trì nếu không dùng nữa.",
        )
    db.delete(room)
    save(db)
