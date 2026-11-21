import calendar
import hashlib
import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.boarding import (
    Contract,
    Invoice,
    InvoiceDueDateHistory,
    InvoiceMonth,
    Payment,
    Property,
    Room,
    TenantProfile,
    UtilityReading,
)
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
from app.services.service_assignment_service import get_effective_services

PRICES = {
    "electricity": "electricity_unit_price",
    "water": "water_unit_price",
    "service": "service_unit_price",
}


def effective_status(total: int, paid: int, due_date: date | None, now: datetime | None = None) -> str:
    today = (now or datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))).astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    if paid >= total:
        return 'paid'
    if due_date is not None and today > due_date:
        return 'overdue'
    return 'partially_paid' if paid > 0 else 'unpaid'


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


def _utility_amount(db: Session, contract: Contract, period: str, prop) -> int:
    readings = {row.utility_type: row for row in db.scalars(select(UtilityReading).where(
        UtilityReading.room_id == contract.room_id, UtilityReading.period == period
    ))}
    services = get_effective_services(db, contract)
    total = 0
    if not services:
        for code, column in PRICES.items():
            reading = readings.get(code)
            if reading is not None:
                total += (reading.current_reading - reading.previous_reading) * getattr(prop, column)
        return total
    for service in services:
        if service.effective_price is None or service.billing_unit is None:
            raise HTTPException(status_code=409, detail=f"Chưa cấu hình giá/đơn vị cho {service.service_name}.")
        quantity = service.quantity
        if service.billing_unit.value in {"kwh", "m3"}:
            reading = readings.get(service.service_code.value)
            if reading is None:
                raise HTTPException(status_code=409, detail=f"Thiếu chỉ số {service.service_name} kỳ {period}.")
            quantity = reading.current_reading - reading.previous_reading
        total += quantity * service.effective_price
    return total


def create_invoice(db: Session, user: User, contract_id: int, data: InvoiceCreate) -> Invoice:
    contract = get_contract(db, contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if contract.status != "active":
        raise HTTPException(status_code=409, detail="Chỉ sinh hóa đơn cho hợp đồng đang hoạt động.")
    year, month = map(int, data.period.split("-"))
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    if contract.start_date > last or contract.end_date < first:
        raise HTTPException(status_code=409, detail="Hợp đồng không có hiệu lực trong tháng này.")
    exists = db.scalar(select(Invoice).join(Contract).where(Contract.room_id == room.id, Invoice.period == data.period))
    if exists is not None:
        raise HTTPException(status_code=409, detail="Hóa đơn của kỳ này đã tồn tại.")
    utility_amount = _utility_amount(db, contract, data.period, prop)
    if contract.monthly_rent + utility_amount > 2_147_483_647:
        raise HTTPException(status_code=422, detail="Tổng tiền vượt giới hạn lưu trữ.")
    db.add(InvoiceMonth(room_id=room.id, period=data.period))
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
        select(
            Payment.invoice_id,
            func.coalesce(func.sum(Payment.amount), 0),
        )
        .where(Payment.invoice_id.in_(invoice_ids))
        .group_by(Payment.invoice_id)
    ).all()

    paid_by_invoice = {
        invoice_id: int(paid or 0)
        for invoice_id, paid in paid_rows
    }

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

        room_number, property_name, tenant_name = metadata_by_invoice.get(
            invoice.id, (None, None, None)
        )

        invoice.paid_amount = paid_amount
        invoice.remaining_amount = remaining_amount
        invoice.effective_status = effective_status(invoice.total_amount, paid_amount, invoice.due_date)
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

    if period is not None:
        query = query.where(Invoice.period == period)

    if contract_id is not None:
        query = query.where(Invoice.contract_id == contract_id)

    query = query.order_by(Invoice.period.desc(), Invoice.id.desc())

    invoices = [
        item for item in db.scalars(query)
        if can_view_invoice(db, user, item)
    ]

    _attach_invoice_details(db, invoices)

    if status is not None:
        invoices = [invoice for invoice in invoices if invoice.effective_status == status]

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
    payments = db.scalars(select(Payment).where(Payment.invoice_id == invoice.id).with_for_update()).all()
    paid_amount = sum(payment.amount for payment in payments)

    if paid_amount <= 0:
        invoice.status = "unpaid"
    elif paid_amount < invoice.total_amount:
        invoice.status = "partially_paid"
    else:
        invoice.status = "paid"

    return invoice.status


def _format_vnd(amount: int) -> str:
    return f"{amount:,}".replace(",", ".") + " đ"

def reconcile_invoice_status(db: Session, user: User, invoice_id: int) -> dict:
    invoice = get_invoice(db, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    invoice = db.scalar(select(Invoice).where(Invoice.id==invoice_id).with_for_update().execution_options(populate_existing=True))
    paid=sum(p.amount for p in db.scalars(select(Payment).where(Payment.invoice_id==invoice_id).with_for_update()))
    if paid > invoice.total_amount:
        raise HTTPException(409,'Tổng thanh toán vượt hóa đơn; cần kiểm tra thủ công.')
    invoice.status = 'unpaid' if paid == 0 else 'paid' if paid == invoice.total_amount else 'partially_paid'
    save(db, invoice)
    return {'id':invoice.id, 'status':invoice.status, 'effective_status':effective_status(invoice.total_amount,paid,invoice.due_date), 'paid_amount':paid, 'remaining_amount':invoice.total_amount-paid}


def update_due_date(db: Session, user: User, invoice_id: int, data) -> dict:
    invoice = get_invoice(db, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update().execution_options(populate_existing=True))
    old = invoice.due_date
    if old != data.due_date:
        invoice.due_date = data.due_date
        db.add(InvoiceDueDateHistory(invoice_id=invoice.id, old_due_date=old, new_due_date=data.due_date, reason=data.reason, changed_by=user.id))
        save(db, invoice)
    paid = sum(payment.amount for payment in db.scalars(select(Payment).where(Payment.invoice_id == invoice.id).with_for_update()))
    return {'id': invoice.id, 'due_date': invoice.due_date, 'effective_status': effective_status(invoice.total_amount, paid, invoice.due_date)}

def record_payment(
    db: Session,
    user: User,
    invoice_id: int,
    data: PaymentCreate,
    idempotency_key: str | None = None,
) -> dict:
    invoice = get_invoice(db, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)

    assert_can_operate(db, user, prop)

    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .with_for_update().execution_options(populate_existing=True)
    )

    if invoice is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy hóa đơn.",
        )

    payments = db.scalars(select(Payment).where(Payment.invoice_id == invoice.id).with_for_update()).all()
    paid_amount = sum(payment.amount for payment in payments)

    fingerprint = hashlib.sha256(json.dumps(data.model_dump(mode='json'), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    key_digest = hashlib.sha256(idempotency_key.encode('ascii')).hexdigest() if idempotency_key is not None else None
    if idempotency_key is not None:
        existing = next((p for p in payments if p.recorded_by == user.id and p.idempotency_key == key_digest), None)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(409, 'Khóa idempotency đã được sử dụng với nội dung khác.')
            return {
                'id': existing.id, 'invoice_id': existing.invoice_id, 'amount': existing.amount,
                'method': existing.method, 'recorded_by': existing.recorded_by, 'paid_at': existing.paid_at,
                'note': existing.note, 'recorded_by_name': user.full_name, 'invoice_status': invoice.status,
                'effective_status': effective_status(invoice.total_amount, paid_amount, invoice.due_date),
                'total_paid': paid_amount, 'remaining_amount': max(invoice.total_amount-paid_amount, 0),
            }

    if invoice.status == "paid" or paid_amount >= invoice.total_amount:
        raise HTTPException(
            status_code=409,
            detail="Hóa đơn đã được thanh toán đủ.",
        )

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
        idempotency_key=key_digest,
        request_fingerprint=fingerprint if idempotency_key is not None else None,
    )

    db.add(payment)
    db.flush()

    total_paid = paid_amount + data.amount
    invoice.status = 'paid' if total_paid >= invoice.total_amount else 'partially_paid'

    save(db, payment, invoice)

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
        "effective_status": effective_status(invoice.total_amount, total_paid, invoice.due_date),
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
