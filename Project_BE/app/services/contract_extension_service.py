import calendar
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, Property, Room, TenantProfile
from app.models.contract_extension import ContractExtension
from app.models.user import User
from app.schemas.boarding import ContractExtend
from app.services.access_scope import assert_can_operate, property_of_room
from app.services.contract_service import (
    _contract_payload,
    _sync_lifecycle,
    _visible,
)
from app.services.db_util import save


MAX_EXTENSION_YEARS = 10


def _latest_end_date(start_date: date) -> date:
    end_year = start_date.year + MAX_EXTENSION_YEARS
    end_day = min(
        start_date.day,
        calendar.monthrange(end_year, start_date.month)[1],
    )
    return date(end_year, start_date.month, end_day)


def extend_contract(
    db: Session,
    user: User,
    contract_id: int,
    data: ContractExtend,
) -> dict:
    contract = db.scalar(
        select(Contract).where(Contract.id == contract_id).with_for_update()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hợp đồng.")

    if not _visible(db, user, contract):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền gia hạn hợp đồng này.",
        )

    _sync_lifecycle(db, contract, persist=False)
    today = date.today()

    if contract.status == "expired":
        raise HTTPException(status_code=409, detail="Hợp đồng đã thanh lý, không thể gia hạn.")
    if contract.status == "pending_liquidation":
        if contract.end_date >= today:
            raise HTTPException(
                status_code=409,
                detail="Hợp đồng đã chấm dứt, không thể gia hạn.",
            )
        if contract.deposit_status in {"returned", "deducted"}:
            raise HTTPException(
                status_code=409,
                detail="Tiền cọc đã hoàn trả hoặc khấu trừ, không thể gia hạn.",
            )
    elif contract.status not in {"active", "created"}:
        raise HTTPException(status_code=409, detail="Hợp đồng không ở trạng thái cho phép gia hạn.")

    if data.new_end_date <= contract.end_date:
        raise HTTPException(
            status_code=422,
            detail="Ngày hết hạn mới phải sau ngày hết hạn hiện tại.",
        )
    if contract.status == "pending_liquidation" and data.new_end_date < today:
        raise HTTPException(
            status_code=422,
            detail="Ngày hết hạn mới phải từ hôm nay trở đi.",
        )
    if data.new_end_date > _latest_end_date(contract.start_date):
        raise HTTPException(
            status_code=422,
            detail="Thời hạn hợp đồng không được vượt quá 10 năm.",
        )

    overlap = db.scalar(
        select(Contract.id).where(
            Contract.room_id == contract.room_id,
            Contract.id != contract.id,
            Contract.status.in_(("active", "created")),
            Contract.start_date <= data.new_end_date,
            Contract.end_date >= contract.start_date,
        )
    )
    if overlap is not None:
        raise HTTPException(
            status_code=409,
            detail="Khoảng thời gian trùng với hợp đồng khác của phòng này.",
        )

    old_end_date = contract.end_date
    old_monthly_rent = contract.monthly_rent
    new_monthly_rent = (
        data.new_monthly_rent
        if data.new_monthly_rent is not None
        else contract.monthly_rent
    )
    if new_monthly_rent == contract.monthly_rent:
        new_monthly_rent = contract.monthly_rent

    contract.end_date = data.new_end_date
    contract.monthly_rent = new_monthly_rent
    if contract.status == "pending_liquidation":
        contract.status = "active"

    room = db.scalar(select(Room).where(Room.id == contract.room_id).with_for_update())
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if contract.status == "active":
        room.status = "occupied"

    extension = ContractExtension(
        contract_id=contract.id,
        old_end_date=old_end_date,
        new_end_date=data.new_end_date,
        old_monthly_rent=old_monthly_rent,
        new_monthly_rent=new_monthly_rent,
        note=data.note,
        extended_by=user.id,
    )
    db.add(extension)
    tenant = db.get(TenantProfile, contract.tenant_id)
    save(db, contract, room, extension)
    return _contract_payload(contract, room, prop, tenant)


def list_extensions(db: Session, user: User, contract_id: int) -> list[dict]:
    contract = db.scalar(
        select(Contract).where(Contract.id == contract_id).with_for_update()
    )
    if contract is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hợp đồng.")
    if not _visible(db, user, contract):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền xem lịch sử gia hạn hợp đồng này.",
        )

    rows = db.execute(
        select(ContractExtension, User.full_name)
        .join(User, User.id == ContractExtension.extended_by)
        .where(ContractExtension.contract_id == contract_id)
        .order_by(ContractExtension.created_at.desc(), ContractExtension.id.desc())
    ).all()
    return [
        {
            "id": extension.id,
            "old_end_date": extension.old_end_date,
            "new_end_date": extension.new_end_date,
            "old_monthly_rent": extension.old_monthly_rent,
            "new_monthly_rent": extension.new_monthly_rent,
            "note": extension.note,
            "extended_by": extension.extended_by,
            "extended_by_name": name,
            "created_at": extension.created_at,
        }
        for extension, name in rows
    ]
