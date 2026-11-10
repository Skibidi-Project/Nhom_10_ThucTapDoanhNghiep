from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, TenantProfile
from app.models.user import User
from app.schemas.boarding import TenantCreate, TenantUpdate
from app.services.access_scope import (
    accessible_landlord_ids,
    assert_can_operate,
    assert_tenant_access,
    get_property,
    get_tenant,
)
from app.services.db_util import save


def _landlord_for_create(db: Session, user: User, data: TenantCreate) -> int:
    if user.role == "landlord":
        return user.id
    if data.property_id is None:
        raise HTTPException(status_code=422, detail="Người quản lý phải chỉ định khu trọ được giao.")
    prop = get_property(db, data.property_id)
    assert_can_operate(db, user, prop)
    return prop.owner_id


def create_tenant(db: Session, user: User, data: TenantCreate) -> TenantProfile:
    if db.scalar(select(TenantProfile).where(TenantProfile.id_number == data.id_number)):
        raise HTTPException(status_code=409, detail="Số CMND/CCCD đã tồn tại.")
    if data.user_id is not None:
        linked_user = db.get(User, data.user_id)
        if linked_user is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản cần liên kết.")
        if db.scalar(select(TenantProfile).where(TenantProfile.user_id == data.user_id)):
            raise HTTPException(status_code=409, detail="Tài khoản này đã được liên kết với một hồ sơ khách thuê.")
    tenant = TenantProfile(
        landlord_id=_landlord_for_create(db, user, data),
        created_by=user.id,
        user_id=data.user_id,
        full_name=data.full_name,
        phone=data.phone,
        id_number=data.id_number,
        email=str(data.email) if data.email else None,
    )
    db.add(tenant)
    save(db, tenant)
    return tenant


def list_tenants(db: Session, user: User) -> list[TenantProfile]:
    landlord_ids = accessible_landlord_ids(db, user)
    if not landlord_ids:
        return []
    return list(db.scalars(
        select(TenantProfile).where(TenantProfile.landlord_id.in_(landlord_ids)).order_by(TenantProfile.id)
    ))


def read_tenant(db: Session, user: User, tenant_id: int) -> TenantProfile:
    tenant = get_tenant(db, tenant_id)
    assert_tenant_access(db, user, tenant)
    return tenant


def update_tenant(db: Session, user: User, tenant_id: int, data: TenantUpdate) -> TenantProfile:
    tenant = read_tenant(db, user, tenant_id)
    if data.full_name is not None:
        tenant.full_name = data.full_name
    if data.phone is not None:
        tenant.phone = data.phone
    if data.email is not None:
        tenant.email = str(data.email)
    save(db, tenant)
    return tenant


def delete_tenant(db: Session, user: User, tenant_id: int) -> None:
    tenant = read_tenant(db, user, tenant_id)
    active = db.scalar(select(Contract.id).where(Contract.tenant_id == tenant.id, Contract.status == "active"))
    if active is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa khách thuê đang có hợp đồng hoạt động.")
    db.delete(tenant)
    save(db)
