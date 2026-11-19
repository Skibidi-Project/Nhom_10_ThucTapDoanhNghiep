from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Contract, Invoice, Property, PropertyManager, Room, TenantProfile
from app.models.user import User


def assigned(db: Session, user_id: int, property_id: int) -> bool:
    row = db.get(PropertyManager, (property_id, user_id))
    return row is not None


def can_operate(db: Session, user: User, prop: Property) -> bool:
    if user.role == Role.LANDLORD.value and prop.owner_id == user.id:
        return True
    if user.role == Role.MANAGER.value and assigned(db, user.id, prop.id):
        return True
    return False


def assert_can_operate(db: Session, user: User, prop: Property) -> None:
    if not can_operate(db, user, prop):
        raise HTTPException(status_code=403, detail="Bạn không có quyền thao tác trên khu trọ này.")


def assert_can_manage(user: User, prop: Property) -> None:
    if user.role != Role.LANDLORD.value or prop.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Chỉ chủ trọ sở hữu khu trọ mới được thực hiện thao tác này.")


def get_property(db: Session, property_id: int) -> Property:
    prop = db.get(Property, property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khu trọ.")
    return prop


def get_room(db: Session, room_id: int) -> Room:
    room = db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng.")
    return room


def get_tenant(db: Session, tenant_id: int) -> TenantProfile:
    tenant = db.get(TenantProfile, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khách thuê.")
    return tenant


def get_contract(db: Session, contract_id: int) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hợp đồng.")
    return contract


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")
    return invoice


def property_of_room(db: Session, room: Room) -> Property:
    return get_property(db, room.property_id)


def accessible_landlord_ids(db: Session, user: User) -> set[int]:
    if user.role == Role.LANDLORD.value:
        return {user.id}
    if user.role == Role.MANAGER.value:
        owner_ids = db.scalars(
            select(Property.owner_id)
            .join(PropertyManager, PropertyManager.property_id == Property.id)
            .where(PropertyManager.user_id == user.id)
        ).all()
        return set(owner_ids)
    return set()


def assert_tenant_access(db: Session, user: User, tenant: TenantProfile) -> None:
    if tenant.landlord_id not in accessible_landlord_ids(db, user):
        raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập hồ sơ khách thuê này.")


def can_view_invoice(db: Session, user: User, invoice: Invoice) -> bool:
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    prop = get_property(db, room.property_id)
    tenant = get_tenant(db, contract.tenant_id)
    if user.role == Role.TENANT.value:
        return tenant.user_id == user.id
    return can_operate(db, user, prop)


def assert_can_view_invoice(db: Session, user: User, invoice: Invoice) -> None:
    if not can_view_invoice(db, user, invoice):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem hóa đơn này.")
