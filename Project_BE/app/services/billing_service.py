from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, Invoice, Payment, Property, Room, TenantProfile, UtilityReading
from app.models.user import User
from app.schemas.boarding import InvoiceCreate, PaymentCreate, ReadingCreate
from app.services.access_scope import (
    assert_can_operate,
    assert_can_view_invoice,
    can_view_invoice,
    get_contract,
    get_invoice,
    get_room,
    property_of_room,
)
from app.services.db_util import save

PRICES = {
    "electricity": "electricity_unit_price",
    "water": "water_unit_price",
    "service": "service_unit_price",
}


def create_reading(db: Session, user: User, room_id: int, data: ReadingCreate) -> UtilityReading:
    room = get_room(db, room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    exists = db.scalar(select(UtilityReading).where(
        UtilityReading.room_id == room.id,
        UtilityReading.utility_type == data.utility_type.value,
        UtilityReading.period == data.period,
    ))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Chỉ số kỳ này đã được ghi.")
    reading = UtilityReading(
        room_id=room.id, utility_type=data.utility_type.value, period=data.period,
        previous_reading=data.previous_reading, current_reading=data.current_reading,
        recorded_by=user.id,
    )
    db.add(reading)
    save(db, reading)
    return reading


def list_readings(db: Session, user: User, room_id: int) -> list[UtilityReading]:
    room = get_room(db, room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    return list(db.scalars(
        select(UtilityReading).where(UtilityReading.room_id == room.id).order_by(UtilityReading.id)
    ))


def _utility_amount(db: Session, room_id: int, period: str, prop) -> int:
    readings = db.scalars(select(UtilityReading).where(
        UtilityReading.room_id == room_id, UtilityReading.period == period
    )).all()
    total = 0
    for reading in readings:
        price = getattr(prop, PRICES[reading.utility_type])
        total += (reading.current_reading - reading.previous_reading) * price
    return total


def create_invoice(db: Session, user: User, contract_id: int, data: InvoiceCreate) -> Invoice:
    contract = get_contract(db, contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if contract.status != "active":
        raise HTTPException(status_code=409, detail="Chỉ sinh hóa đơn cho hợp đồng đang hoạt động.")
    exists = db.scalar(select(Invoice).where(Invoice.contract_id == contract.id, Invoice.period == data.period))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Hóa đơn của kỳ này đã tồn tại.")
    utility_amount = _utility_amount(db, room.id, data.period, prop)
    invoice = Invoice(
        contract_id=contract.id, period=data.period, rent_amount=contract.monthly_rent,
        utility_amount=utility_amount, total_amount=contract.monthly_rent + utility_amount, status="unpaid",
    )
    db.add(invoice)
    save(db, invoice)
    return invoice


def _attach_invoice_details(db: Session, invoices: list[Invoice]) -> None:
    if not invoices:
        return
    invoice_ids = [invoice.id for invoice in invoices]
    paid_rows = db.execute(
        select(Payment.invoice_id, func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.invoice_id.in_(invoice_ids))
        .group_by(Payment.invoice_id)
    ).all()
    paid_by_invoice = {invoice_id: int(paid or 0) for invoice_id, paid in paid_rows}

    metadata_rows = db.execute(
        select(
            Invoice.id,
            Room.room_number,
            Property.name,
            TenantProfile.full_name,
        )
        .join(Contract, Contract.id == Invoice.contract_id)
        .join(Room, Room.id == Contract.room_id)
        .join(Property, Property.id == Room.property_id)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(Invoice.id.in_(invoice_ids))
    ).all()
    metadata_by_invoice = {
        invoice_id: (room_number, property_name, tenant_name)
        for invoice_id, room_number, property_name, tenant_name in metadata_rows
    }

    for invoice in invoices:
        paid_amount = paid_by_invoice.get(invoice.id, 0)
        remaining_amount = max(invoice.total_amount - paid_amount, 0)
        room_number, property_name, tenant_name = metadata_by_invoice.get(invoice.id, (None, None, None))
        invoice.paid_amount = paid_amount
        invoice.remaining_amount = remaining_amount
        invoice.room_number = room_number
        invoice.property_name = property_name
        invoice.tenant_name = tenant_name


def list_invoices(
    db: Session,
    user: User,
    status: str | None = None,
    period: str | None = None,
    contract_id: int | None = None,
) -> list[Invoice]:
    query = select(Invoice)
    if status is not None:
        query = query.where(Invoice.status == status)
    if period is not None:
        query = query.where(Invoice.period == period)
    if contract_id is not None:
        query = query.where(Invoice.contract_id == contract_id)
    query = query.order_by(Invoice.period.desc(), Invoice.id.desc())
    invoices = [item for item in db.scalars(query) if can_view_invoice(db, user, item)]
    _attach_invoice_details(db, invoices)
    return invoices


def read_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)
    _attach_invoice_details(db, [invoice])
    return invoice


def _paid_amount(db: Session, invoice_id: int) -> int:
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id))
    return int(paid or 0)


def recompute_invoice_status(db: Session, invoice: Invoice) -> str:
    paid_amount = _paid_amount(db, invoice.id)
    if paid_amount <= 0:
        invoice.status = "unpaid"
    elif paid_amount < invoice.total_amount:
        invoice.status = "partially_paid"
    else:
        invoice.status = "paid"
    return invoice.status


def _format_vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đ"


def record_payment(db: Session, user: User, invoice_id: int, data: PaymentCreate) -> dict:
    invoice = get_invoice(db, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)

    invoice = db.scalar(
        select(Invoice).where(Invoice.id == invoice_id).with_for_update()
    )
    if invoice is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn.")
    paid_amount = _paid_amount(db, invoice.id)
    if invoice.status == "paid" or paid_amount >= invoice.total_amount:
        raise HTTPException(status_code=409, detail="Hóa đơn đã được thanh toán đủ.")
    remaining = invoice.total_amount - paid_amount
    if data.amount > remaining:
        raise HTTPException(
            status_code=409,
            detail=f"Số tiền vượt quá số còn nợ (còn thiếu {_format_vnd(remaining)}).",
        )
    payment = Payment(
        invoice_id=invoice.id,
        amount=data.amount,
        method=data.method,
        recorded_by=user.id,
        paid_at=data.paid_at or datetime.now(),
        note=data.note,
    )
    db.add(payment)
    db.flush()
    recompute_invoice_status(db, invoice)
    save(db, payment, invoice)
    total_paid = _paid_amount(db, invoice.id)
    return {
        "id": payment.id,
        "invoice_id": payment.invoice_id,
        "amount": payment.amount,
        "method": payment.method,
        "recorded_by": payment.recorded_by,
        "paid_at": payment.paid_at,
        "note": payment.note,
        "recorded_by_name": user.full_name,
        "invoice_status": invoice.status,
        "total_paid": total_paid,
        "remaining_amount": max(invoice.total_amount - total_paid, 0),
    }


def list_payments(db: Session, user: User, invoice_id: int) -> list[dict]:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)
    rows = db.execute(
        select(Payment, User.full_name)
        .join(User, User.id == Payment.recorded_by)
        .where(Payment.invoice_id == invoice_id)
        .order_by(Payment.paid_at.desc(), Payment.id.desc())
    ).all()
    return [
        {
            "id": payment.id,
            "invoice_id": payment.invoice_id,
            "amount": payment.amount,
            "method": payment.method,
            "paid_at": payment.paid_at,
            "note": payment.note,
            "recorded_by": payment.recorded_by,
            "recorded_by_name": recorded_by_name,
        }
        for payment, recorded_by_name in rows
    ]


def list_own_invoices(db: Session, user: User) -> list[Invoice]:
    invoices = list(db.scalars(
        select(Invoice)
        .join(Contract, Contract.id == Invoice.contract_id)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(TenantProfile.user_id == user.id)
        .order_by(Invoice.period.desc(), Invoice.id.desc())
    ))
    _attach_invoice_details(db, invoices)
    return invoices
