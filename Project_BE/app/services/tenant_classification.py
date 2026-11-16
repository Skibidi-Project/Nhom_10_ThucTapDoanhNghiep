from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, TenantProfile
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.services.access_scope import (
    assert_can_operate, get_room, get_tenant, property_of_room,
)
from app.services.db_util import save


def _context(db: Session, user: User, contract_id: int, *, write: bool = False):
    statement = select(Contract).where(Contract.id == contract_id)
    if write:
        # Kh?a h?p ??ng ?? c?c thao t?c th?m/x?a th?nh vi?n ???c tu?n t? h?a.
        statement = statement.with_for_update()
    contract = db.scalar(statement)
    if contract is None:
        raise HTTPException(404, "Kh?ng t?m th?y h?p ??ng.")
    prop = property_of_room(db, get_room(db, contract.room_id))
    assert_can_operate(db, user, prop)
    if write and (
        contract.status not in {"created", "active"} or contract.end_date < date.today()
    ):
        # Gi? nguy?n danh s?ch l?ch s?, kh?ng s?a tr?ng th?i h?p ??ng c?a US kh?c.
        raise HTTPException(409, "Kh?ng th? s?a th?nh vi?n c?a h?p ??ng ?? k?t th?c ho?c ch? thanh l?.")
    return contract, prop


def _item(tenant: TenantProfile, classification: str) -> dict:
    return {"tenant_id": tenant.id, "full_name": tenant.full_name,
            "classification": classification}


def list_group(db: Session, user: User, contract_id: int) -> dict:
    contract, _ = _context(db, user, contract_id)
    members = db.scalars(
        select(TenantProfile).join(TenantMember, TenantMember.tenant_id == TenantProfile.id)
        .where(TenantMember.contract_id == contract.id).order_by(TenantProfile.id)
    ).all()
    return {
        "contract_id": contract.id, "room_id": contract.room_id,
        "representative": _item(get_tenant(db, contract.tenant_id), "representative"),
        "members": [_item(tenant, "member") for tenant in members],
    }


def add_member(db: Session, user: User, contract_id: int, tenant_id: int) -> dict:
    contract, prop = _context(db, user, contract_id, write=True)
    tenant = get_tenant(db, tenant_id)
    if tenant.landlord_id != prop.owner_id:
        raise HTTPException(403, "Kh?ch thu? kh?ng thu?c ch? tr? s? h?u khu tr? n?y.")
    if tenant.id == contract.tenant_id:
        raise HTTPException(409, "Ng??i ??i di?n kh?ng th? ??ng th?i l? th?nh vi?n.")
    if db.get(TenantMember, (contract.id, tenant.id)) is not None:
        raise HTTPException(409, "Kh?ch thu? ?? l? th?nh vi?n c?a h?p ??ng.")
    db.add(TenantMember(contract_id=contract.id, tenant_id=tenant.id))
    save(db)
    return _item(tenant, "member")


def remove_member(db: Session, user: User, contract_id: int, tenant_id: int) -> None:
    contract, _ = _context(db, user, contract_id, write=True)
    if tenant_id == contract.tenant_id:
        raise HTTPException(409, "Kh?ng th? lo?i ng??i ??i di?n kh?i h?p ??ng.")
    member = db.get(TenantMember, (contract.id, tenant_id))
    if member is None:
        raise HTTPException(404, "Kh?ng t?m th?y th?nh vi?n trong h?p ??ng.")
    # Ch? x?a li?n k?t, lu?n gi? nguy?n h? s? kh?ch thu?.
    db.delete(member)
    save(db)
