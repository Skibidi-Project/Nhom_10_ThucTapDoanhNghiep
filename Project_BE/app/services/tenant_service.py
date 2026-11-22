from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Contract, TenantProfile
from app.models.user import User
from app.schemas.boarding import TenantAccountLinkResponse, TenantCreate, TenantUpdate
from app.schemas.user import UserLogin
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
        id_issue_date=data.id_issue_date,
        id_issue_place=data.id_issue_place,
        hometown=data.hometown,
        email=str(data.email) if data.email else None,
    )
    db.add(tenant)
    save(db, tenant)
    return tenant


def list_tenants(
    db: Session,
    user: User,
    q: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[TenantProfile] | dict:
    landlord_ids = accessible_landlord_ids(db, user)
    statement = select(TenantProfile).where(TenantProfile.landlord_id.in_(landlord_ids))

    search = q.strip() if q else ""
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                TenantProfile.full_name.like(pattern, escape="\\"),
                TenantProfile.phone.like(pattern, escape="\\"),
                TenantProfile.id_number.like(pattern, escape="\\"),
            )
        )

    paginated = page is not None or page_size is not None
    if not paginated:
        return list(db.scalars(statement.order_by(TenantProfile.id)))

    current_page = page or 1
    current_page_size = page_size or 10
    total = db.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0
    items = list(db.scalars(
        statement.order_by(TenantProfile.id.desc())
        .offset((current_page - 1) * current_page_size)
        .limit(current_page_size)
    ))
    return {
        "items": items,
        "total": total,
        "page": current_page,
        "page_size": current_page_size,
    }


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
    if data.id_number is not None and data.id_number != tenant.id_number:
        duplicate = db.scalar(select(TenantProfile.id).where(TenantProfile.id_number == data.id_number))
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Số CMND/CCCD đã tồn tại.")
        tenant.id_number = data.id_number
    for field in ("id_issue_date", "id_issue_place", "hometown"):
        if field in data.model_fields_set:
            setattr(tenant, field, getattr(data, field))
    save(db, tenant)
    return tenant


def delete_tenant(db: Session, user: User, tenant_id: int) -> None:
    tenant = read_tenant(db, user, tenant_id)
    active = db.scalar(select(Contract.id).where(Contract.tenant_id == tenant.id, Contract.status == "active"))
    if active is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa khách thuê đang có hợp đồng hoạt động.")
    db.delete(tenant)
    save(db)


def resolve_account_by_identifier(db: Session, identifier: str) -> User:
    candidate = UserLogin.model_validate({"identifier": identifier, "password": "placeholder"})
    value = candidate.identifier
    column = User.email if "@" in value else User.phone
    user = db.scalar(select(User).where(column == value))
    if user is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản với email/SĐT này.")
    return user


def link_tenant_account(db: Session, user: User, tenant_id: int, identifier: str) -> TenantAccountLinkResponse:
    if user.role == Role.TENANT.value:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện thao tác này.")
    tenant = read_tenant(db, user, tenant_id)
    account = resolve_account_by_identifier(db, identifier)
    if account.role != Role.TENANT.value:
        raise HTTPException(status_code=409, detail="Chỉ liên kết được tài khoản có vai trò khách thuê.")
    if db.scalar(select(TenantProfile.id).where(TenantProfile.user_id == account.id)) is not None:
        raise HTTPException(status_code=409, detail="Tài khoản này đã được liên kết với một hồ sơ khách thuê.")
    if tenant.user_id is not None:
        raise HTTPException(status_code=409, detail="Hồ sơ này đã liên kết tài khoản. Hãy gỡ liên kết trước.")
    tenant.user_id = account.id
    save(db, tenant)
    return TenantAccountLinkResponse(tenant_id=tenant.id, user_id=account.id, full_name=account.full_name, email=account.email)


def unlink_tenant_account(db: Session, user: User, tenant_id: int) -> None:
    if user.role == Role.TENANT.value:
        raise HTTPException(status_code=403, detail="Bạn không có quyền thực hiện thao tác này.")
    tenant = read_tenant(db, user, tenant_id)
    if tenant.user_id is None:
        raise HTTPException(status_code=404, detail="Hồ sơ khách thuê chưa liên kết tài khoản.")
    tenant.user_id = None
    save(db, tenant)
