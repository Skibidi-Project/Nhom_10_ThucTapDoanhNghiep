import calendar
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, ContractRenewalHistory, Invoice, Property, PropertyManager, Room, TenantProfile, UtilityPriceHistory
from app.models.service_assignment import ServiceAssignment
from app.models.user import User
from app.schemas.boarding import (
    ALLOWED_PAYMENT_CYCLES,
    ContractCreate,
    ContractRenewalCreate,
    ContractRenewalResponse,
)
from app.services.access_scope import assert_can_operate, get_contract, get_property, get_room, get_tenant, property_of_room
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
        "deposit_status": contract.deposit_status,
        "deposit_returned_amount": contract.deposit_returned_amount,
        "deposit_note": contract.deposit_note,
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
        payment_cycle_months=data.payment_cycle_months,
        status="active" if data.start_date <= date.today() else "created",
    )
    room.status = "occupied"
    db.add(contract)
    save(db, contract, room)
    return _contract_payload(contract, room, prop, tenant)


def list_contracts(
    db: Session,
    user: User,
    property_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[dict] | dict:
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

    if property_id is not None:
        prop = get_property(db, property_id)
        assert_can_operate(db, user, prop)
        statement = statement.where(Property.id == property_id)

    search = q.strip() if q else ""
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                Room.room_number.like(pattern, escape="\\"),
                TenantProfile.full_name.like(pattern, escape="\\"),
            )
        )

    paginated = page is not None or page_size is not None
    order_by = Contract.id.desc() if paginated else Contract.id.asc()
    rows = db.execute(statement.order_by(order_by)).all()
    for contract, _, _, _ in rows:
        _sync_lifecycle(db, contract)

    filtered = [
        (contract, room, prop, tenant)
        for contract, room, prop, tenant in rows
        if status is None or contract.status == status
    ]

    if not paginated:
        return [
            _contract_payload(contract, room, prop, tenant)
            for contract, room, prop, tenant in filtered
        ]

    current_page = page or 1
    current_page_size = page_size or 10
    total = len(filtered)
    # Dữ liệu quy mô đồ án; cắt trang trong bộ nhớ sau khi đồng bộ và lọc trạng thái.
    start = (current_page - 1) * current_page_size
    sliced = filtered[start:start + current_page_size]
    return {
        "items": [
            _contract_payload(contract, room, prop, tenant)
            for contract, room, prop, tenant in sliced
        ],
        "total": total,
        "page": current_page,
        "page_size": current_page_size,
    }


def read_contract(db: Session, user: User, contract_id: int) -> dict:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem hợp đồng này.")
    _sync_lifecycle(db, contract)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    tenant = get_tenant(db, contract.tenant_id)
    return _contract_payload(contract, room, prop, tenant)


def _latest_allowed_end(start_date: date) -> date:
    end_year = start_date.year + 10
    return date(
        end_year,
        start_date.month,
        min(start_date.day, calendar.monthrange(end_year, start_date.month)[1]),
    )


def renew_contract(
    db: Session, user: User, contract_id: int, data: ContractRenewalCreate
) -> dict:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Bạn không có quyền gia hạn hợp đồng này.")
    _sync_lifecycle(db, contract)
    if contract.status != "active":
        raise HTTPException(
            status_code=409, detail="Chỉ gia hạn được hợp đồng đang hiệu lực."
        )

    if data.new_end_date <= contract.end_date:
        raise HTTPException(
            status_code=409,
            detail="Ngày kết thúc mới phải sau ngày kết thúc hiện tại của hợp đồng.",
        )

    latest_end = _latest_allowed_end(contract.start_date)
    if data.new_end_date > latest_end:
        raise HTTPException(
            status_code=409,
            detail=f"Thời gian gia hạn không được vượt quá 10 năm kể từ ngày bắt đầu ({latest_end.isoformat()}).",
        )

    new_monthly_rent = data.new_monthly_rent if data.new_monthly_rent is not None else contract.monthly_rent
    new_payment_cycle = (
        data.new_payment_cycle_months
        if data.new_payment_cycle_months is not None
        else contract.payment_cycle_months
    )
    if new_monthly_rent <= 0:
        raise HTTPException(status_code=409, detail="Tiền thuê hàng tháng phải lớn hơn 0.")
    if new_payment_cycle not in ALLOWED_PAYMENT_CYCLES:
        raise HTTPException(
            status_code=409,
            detail="Kỳ thanh toán chỉ được là 1, 2, 3, 6 hoặc 12 tháng.",
        )

    overlap = db.scalar(
        select(Contract.id).where(
            Contract.room_id == contract.room_id,
            Contract.id != contract.id,
            Contract.status == "active",
            Contract.start_date <= data.new_end_date,
            Contract.end_date >= contract.start_date,
        )
    )
    if overlap is not None:
        raise HTTPException(
            status_code=409,
            detail="Khoảng thời gian gia hạn trùng với hợp đồng khác của phòng này.",
        )

    history = ContractRenewalHistory(
        contract_id=contract.id,
        previous_end_date=contract.end_date,
        new_end_date=data.new_end_date,
        previous_monthly_rent=contract.monthly_rent,
        new_monthly_rent=new_monthly_rent,
        previous_payment_cycle_months=contract.payment_cycle_months,
        new_payment_cycle_months=new_payment_cycle,
        renewal_note=data.note.strip() if data.note else None,
        renewed_by=user.id,
    )
    db.add(history)
    contract.end_date = data.new_end_date
    contract.monthly_rent = new_monthly_rent
    contract.payment_cycle_months = new_payment_cycle
    # Ghi lịch sử trước, cập nhật hợp đồng sau. Nếu bất kỳ bước nào thất bại,
    # save() sẽ rollback toàn bộ giao dịch, hợp đồng không bị thay đổi.
    save(db, history, contract)

    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    tenant = get_tenant(db, contract.tenant_id)
    return _contract_payload(contract, room, prop, tenant)


def list_renewals(db: Session, user: User, contract_id: int) -> list[ContractRenewalResponse]:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem lịch sử gia hạn hợp đồng này.")
    rows = db.execute(
        select(ContractRenewalHistory, User.full_name)
        .join(User, User.id == ContractRenewalHistory.renewed_by)
        .where(ContractRenewalHistory.contract_id == contract_id)
        .order_by(ContractRenewalHistory.id.desc())
    ).all()
    return [
        ContractRenewalResponse(
            id=row.id,
            contract_id=row.contract_id,
            previous_end_date=row.previous_end_date,
            new_end_date=row.new_end_date,
            previous_monthly_rent=row.previous_monthly_rent,
            new_monthly_rent=row.new_monthly_rent,
            previous_payment_cycle_months=row.previous_payment_cycle_months,
            new_payment_cycle_months=row.new_payment_cycle_months,
            renewal_note=row.renewal_note,
            renewed_by=row.renewed_by,
            renewed_by_name=name,
            renewed_at=row.renewed_at,
        )
        for row, name in rows
    ]


def terminate_contract(db: Session, user: User, contract_id: int) -> dict:
    read_contract(db, user, contract_id)
    contract = get_contract(db, contract_id)
    if contract.status not in {"active", "created"}:
        raise HTTPException(status_code=409, detail="Chỉ chấm dứt được hợp đồng đang hoạt động.")
    room = get_room(db, contract.room_id)
    contract.status = "pending_liquidation"
    save(db, contract)
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
    for contract, _, _, _ in rows:
        _sync_lifecycle(db, contract)
    return [_contract_payload(contract, room, prop, tenant) for contract, room, prop, tenant in rows]


def _sync_lifecycle(db: Session, contract: Contract) -> None:
    if contract.status == "created" and contract.start_date <= date.today():
        contract.status = "active"
        save(db, contract)
    elif contract.status == "active" and contract.end_date < date.today():
        contract.status = "pending_liquidation"
        save(db, contract)


def update_deposit(db: Session, user: User, contract_id: int, data) -> dict:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Kh\u00f4ng c\u00f3 quy\u1ec1n c\u1eadp nh\u1eadt h\u1ee3p \u0111\u1ed3ng n\u00e0y.")
    _sync_lifecycle(db, contract)
    if contract.status == "expired":
        raise HTTPException(status_code=409, detail="H\u1ee3p \u0111\u1ed3ng \u0111\u00e3 h\u1ebft h\u1ea1n v\u00e0 kh\u00f4ng th\u1ec3 s\u1eeda ti\u1ec1n c\u1ecdc.")
    if data.status in {"returned", "deducted"} and contract.status != "pending_liquidation":
        raise HTTPException(status_code=409, detail="Ch\u1ec9 ho\u00e0n tr\u1ea3 ho\u1eb7c kh\u1ea5u tr\u1eeb c\u1ecdc khi h\u1ee3p \u0111\u1ed3ng ch\u1edd thanh l\u00fd.")
    if data.status == "not_applicable" and contract.deposit != 0:
        raise HTTPException(status_code=409, detail="Ch\u1ec9 ch\u1ecdn not_applicable khi h\u1ee3p \u0111\u1ed3ng kh\u00f4ng c\u00f3 ti\u1ec1n c\u1ecdc.")
    if data.returned_amount > contract.deposit:
        raise HTTPException(status_code=422, detail="Ti\u1ec1n c\u1ecdc ho\u00e0n tr\u1ea3 kh\u00f4ng \u0111\u01b0\u1ee3c v\u01b0\u1ee3t qu\u00e1 ti\u1ec1n c\u1ecdc.")
    contract.deposit_status = data.status
    contract.deposit_returned_amount = data.returned_amount
    contract.deposit_note = data.note.strip() if data.note else None
    save(db, contract)
    room = get_room(db, contract.room_id)
    return _contract_payload(contract, room, property_of_room(db, room), get_tenant(db, contract.tenant_id))


def liquidate_contract(db: Session, user: User, contract_id: int) -> dict:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="Không có quyền thanh lý hợp đồng này.")
    _sync_lifecycle(db, contract)
    if contract.status != "pending_liquidation":
        raise HTTPException(status_code=409, detail="Hợp đồng chưa ở trạng thái chờ thanh lý.")
    if contract.deposit_status == "unpaid" and contract.deposit > 0:
        raise HTTPException(status_code=409, detail="Cần ghi nhận tình trạng tiền cọc trước khi hoàn tất thanh lý.")
    contract.status = "expired"
    room = get_room(db, contract.room_id)
    room.status = "available"
    save(db, contract, room)
    return _contract_payload(contract, room, property_of_room(db, room), get_tenant(db, contract.tenant_id))


def delete_expired_contract(db: Session, user: User, contract_id: int) -> None:
    contract = get_contract(db, contract_id)
    if not _visible(db, user, contract):
        raise HTTPException(status_code=403, detail="B\u1ea1n kh\u00f4ng c\u00f3 quy\u1ec1n x\u00f3a h\u1ee3p \u0111\u1ed3ng n\u00e0y.")
    if contract.status != "expired":
        raise HTTPException(status_code=409, detail="Ch\u1ec9 x\u00f3a \u0111\u01b0\u1ee3c h\u1ee3p \u0111\u1ed3ng \u0111\u00e3 h\u1ebft h\u1ea1n v\u00e0 ho\u00e0n t\u1ea5t thanh l\u00fd.")

    invoice_id = db.scalar(select(Invoice.id).where(Invoice.contract_id == contract.id).limit(1))
    if invoice_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Kh\u00f4ng th\u1ec3 x\u00f3a h\u1ee3p \u0111\u1ed3ng \u0111\u00e3 c\u00f3 h\u00f3a \u0111\u01a1n \u0111\u1ec3 b\u1ea3o to\u00e0n l\u1ecbch s\u1eed thanh to\u00e1n.",
        )

    db.execute(delete(ServiceAssignment).where(ServiceAssignment.contract_id == contract.id))
    db.execute(
        delete(UtilityPriceHistory).where(UtilityPriceHistory.contract_id == contract.id)
    )
    db.delete(contract)
    save(db)
