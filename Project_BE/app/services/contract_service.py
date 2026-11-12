from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, Property, PropertyManager, Room, TenantProfile
from app.models.user import User
from app.schemas.boarding import ContractCreate
from app.services.access_scope import assert_can_operate, get_contract, get_room, get_tenant, property_of_room
from app.services.db_util import save


def _contract_payload(contract: Contract, room: Room, prop: Property, tenant: TenantProfile) -> dict:
    return {
        "id": contract.id,
        "room_id": contract.room_id,
        "tenant_id": contract.tenant_id,
        "created_by": contract.created_by,
        "start_date": contract.start_date,
        "end_date": contract.end_date,
        "deposit": contract.deposit,
        "monthly_rent": contract.monthly_rent,
        "payment_cycle_months": contract.payment_cycle_months,
        "status": contract.status,
        "room_number": room.room_number,
        "property_id": prop.id,
        "property_name": prop.name,
        "tenant_name": tenant.full_name,
    }


def _visible(db: Session, user: User, contract: Contract) -> bool:
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    try:
        assert_can_operate(db, user, prop)
        return True
    except HTTPException:
        return False


def create_contract(db: Session, user: User, data: ContractCreate) -> dict:
    room = db.scalar(select(Room).where(Room.id == data.room_id).with_for_update())
    if room is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng.")
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    tenant = get_tenant(db, data.tenant_id)
    if tenant.landlord_id != prop.owner_id:
        raise HTTPException(status_code=403, detail="Khách thuê không thuộc khu trọ này.")
    overlap = db.scalar(
        select(Contract.id).where(
            Contract.room_id == room.id,
            Contract.status == "active",
            Contract.start_date <= data.end_date,
            Contract.end_date >= data.start_date,
        )
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="Khoảng thời gian trùng với hợp đồng khác của phòng này.")
    if room.status != "available":
        raise HTTPException(status_code=409, detail="Chỉ tạo hợp đồng cho phòng đang trống.")
    active = db.scalar(
        select(Contract.id).where(Contract.room_id == room.id, Contract.status == "active")
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Phòng đã có hợp đồng đang hoạt động.")
    contract = Contract(
        room_id=room.id, tenant_id=tenant.id, created_by=user.id,
        start_date=data.start_date, end_date=data.end_date,
        deposit=data.deposit, monthly_rent=data.monthly_rent,
        payment_cycle_months=data.payment_cycle_months, status="active",
    )
    room.status = "occupied"
    db.add(contract)
    save(db, contract, room)
    return _contract_payload(contract, room, prop, tenant)


def list_contracts(db: Session, user: User) -> list[dict]:
    statement = (
        select(Contract, Room, Property, TenantProfile)
        .join(Room, Room.id == Contract.room_id)
        .join(Property, Property.id == Room.property_id)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
    )
    if user.role == "landlord":
        statement = statement.where(Property.owner_id == user.id)
    elif user.role == "manager":
        statement = statement.join(
            PropertyManager, PropertyManager.property_id == Property.id
        ).where(PropertyManager.user_id == user.id)
    else:
        return []
    rows = db.execute(statement.order_by(Contract.id)).all()
    return [_contract_payload(contract, room, prop, tenant) for contract, room, prop, tenant in rows]


def read_contract(db: Session, user: User, contract_id: int) -> dict:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem hợp đồng này.")
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    tenant = get_tenant(db, contract.tenant_id)
    return _contract_payload(contract, room, prop, tenant)


def terminate_contract(db: Session, user: User, contract_id: int) -> dict:
    read_contract(db, user, contract_id)
    contract = get_contract(db, contract_id)
    if contract.status != "active":
        raise HTTPException(status_code=409, detail="Chỉ chấm dứt được hợp đồng đang hoạt động.")
    room = get_room(db, contract.room_id)
    contract.status = "terminated"
    room.status = "available"
    save(db, contract, room)
    prop = property_of_room(db, room)
    tenant = get_tenant(db, contract.tenant_id)
    return _contract_payload(contract, room, prop, tenant)


def list_own_contracts(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(Contract, Room, Property, TenantProfile)
        .join(Room, Room.id == Contract.room_id)
        .join(Property, Property.id == Room.property_id)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(TenantProfile.user_id == user.id)
        .order_by(Contract.id)
    ).all()
    return [_contract_payload(contract, room, prop, tenant) for contract, room, prop, tenant in rows]
