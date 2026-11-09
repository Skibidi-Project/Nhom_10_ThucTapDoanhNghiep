from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, TenantProfile
from app.models.user import User
from app.schemas.boarding import ContractCreate
from app.services.access_scope import assert_can_operate, get_contract, get_room, get_tenant, property_of_room
from app.services.db_util import save


def _visible(db: Session, user: User, contract: Contract) -> bool:
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    try:
        assert_can_operate(db, user, prop)
        return True
    except HTTPException:
        return False


def create_contract(db: Session, user: User, data: ContractCreate) -> Contract:
    room = get_room(db, data.room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    tenant = get_tenant(db, data.tenant_id)
    if tenant.landlord_id != prop.owner_id:
        raise HTTPException(status_code=403, detail="Khách thuê không thuộc khu trọ này.")
    if room.status != "available":
        raise HTTPException(status_code=409, detail="Chỉ tạo hợp đồng cho phòng đang trống.")
    active = db.scalar(select(Contract.id).where(Contract.room_id == room.id, Contract.status == "active"))
    if active is not None:
        raise HTTPException(status_code=409, detail="Phòng đã có hợp đồng đang hoạt động.")
    contract = Contract(
        room_id=room.id, tenant_id=tenant.id, created_by=user.id,
        start_date=data.start_date, end_date=data.end_date,
        deposit=data.deposit, monthly_rent=data.monthly_rent, status="active",
    )
    room.status = "occupied"
    db.add(contract)
    save(db, contract, room)
    return contract


def list_contracts(db: Session, user: User) -> list[Contract]:
    return [item for item in db.scalars(select(Contract).order_by(Contract.id)) if _visible(db, user, item)]


def read_contract(db: Session, user: User, contract_id: int) -> Contract:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem hợp đồng này.")
    return contract


def terminate_contract(db: Session, user: User, contract_id: int) -> Contract:
    contract = read_contract(db, user, contract_id)
    if contract.status != "active":
        raise HTTPException(status_code=409, detail="Chỉ chấm dứt được hợp đồng đang hoạt động.")
    room = get_room(db, contract.room_id)
    contract.status = "terminated"
    room.status = "available"
    save(db, contract, room)
    return contract


def list_own_contracts(db: Session, user: User) -> list[Contract]:
    return list(db.scalars(
        select(Contract)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(TenantProfile.user_id == user.id)
        .order_by(Contract.id)
    ))
