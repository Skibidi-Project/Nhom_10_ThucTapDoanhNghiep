from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.boarding import Contract, Invoice, Payment, TenantProfile, UtilityReading
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


def list_invoices(db: Session, user: User) -> list[Invoice]:
    return [item for item in db.scalars(select(Invoice).order_by(Invoice.id)) if can_view_invoice(db, user, item)]


def read_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)
    return invoice


def _paid_amount(db: Session, invoice_id: int) -> int:
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id))
    return int(paid or 0)


def record_payment(db: Session, user: User, invoice_id: int, data: PaymentCreate) -> Payment:
    invoice = read_invoice(db, user, invoice_id)
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="Hóa đơn đã được thanh toán đủ.")
    remaining = invoice.total_amount - _paid_amount(db, invoice.id)
    if data.amount > remaining:
        raise HTTPException(status_code=409, detail="Số tiền thanh toán vượt quá số còn nợ.")
    payment = Payment(invoice_id=invoice.id, amount=data.amount, method=data.method.strip(), recorded_by=user.id)
    db.add(payment)
    paid_after = remaining - data.amount
    invoice.status = "paid" if paid_after == 0 else "partially_paid"
    save(db, payment, invoice)
    return payment


def list_own_invoices(db: Session, user: User) -> list[Invoice]:
    return list(db.scalars(
        select(Invoice)
        .join(Contract, Contract.id == Invoice.contract_id)
        .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
        .where(TenantProfile.user_id == user.id)
        .order_by(Invoice.id)
    ))
