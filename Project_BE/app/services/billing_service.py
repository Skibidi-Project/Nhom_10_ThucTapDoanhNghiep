import calendar
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select, insert, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.boarding import Contract, Invoice, InvoiceMonth, Payment, Room, TenantProfile, UtilityReading
from app.db.reading_revision import reading_revision
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


def _lock_room(db: Session, room_id: int) -> Room:
    room = db.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng.")
    return room


def _invoice_for_room_period(db: Session, room_id: int, period: str) -> bool:
    return db.scalar(select(Invoice.id).join(Contract).where(
        Contract.room_id == room_id, Invoice.period == period
    ).limit(1).with_for_update()) is not None


def create_reading(db: Session, user: User, room_id: int, data: ReadingCreate) -> UtilityReading:
    room = _lock_room(db, room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if _invoice_for_room_period(db, room.id, data.period):
        raise HTTPException(status_code=409, detail="Kỳ này đã có hóa đơn; không thể ghi chỉ số.")
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


def reading_version(db: Session, user: User, room_id: int, reading_id: int) -> int:
    room = get_room(db, room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    row = db.scalar(select(UtilityReading).where(UtilityReading.id == reading_id, UtilityReading.room_id == room_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy chỉ số của phòng.")
    try:
        version = db.scalar(select(reading_revision.c.version).where(reading_revision.c.reading_id == reading_id))
        return version if version is not None else 0
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Chưa áp dụng migration phiên bản chỉ số.") from exc


def update_reading(db: Session, user: User, room_id: int, reading_id: int, data):
    try:
        room = _lock_room(db, room_id)
        assert_can_operate(db, user, property_of_room(db, room))
        row = db.scalar(select(UtilityReading).where(UtilityReading.id == reading_id, UtilityReading.room_id == room_id).with_for_update())
        if row is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy chỉ số của phòng.")
        if row.utility_type not in {"electricity", "water"}:
            raise HTTPException(status_code=422, detail="Chỉ hỗ trợ cập nhật chỉ số điện hoặc nước.")
        if _invoice_for_room_period(db, room.id, row.period):
            raise HTTPException(status_code=409, detail="Kỳ này đã có hóa đơn; không thể sửa chỉ số.")
        version = db.scalar(select(reading_revision.c.version).where(reading_revision.c.reading_id == reading_id).with_for_update())
        if (version or 0) != data.expected_version:
            raise HTTPException(status_code=409, detail="Chỉ số đã thay đổi; vui lòng tải lại.")
        row.previous_reading = data.previous_reading
        row.current_reading = data.current_reading
        if version is None:
            db.execute(insert(reading_revision).values(reading_id=reading_id, version=1))
        else:
            db.execute(update(reading_revision).where(reading_revision.c.reading_id == reading_id).values(version=version + 1))
        save(db, row)
        return row
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Không thể cập nhật; kiểm tra migration chỉ số.") from exc


def _utility_amount(db: Session, contract: Contract, period: str, prop) -> int:
    readings = {row.utility_type: row for row in db.scalars(select(UtilityReading).where(
        UtilityReading.room_id == contract.room_id, UtilityReading.period == period
    ).with_for_update())}
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
    assigned = {service.service_code.value for service in services}
    for code in ("electricity", "water"):
        if code not in assigned and (reading := readings.get(code)) is not None:
            total += (reading.current_reading - reading.previous_reading) * getattr(prop, PRICES[code])
    return total


def create_invoice(db: Session, user: User, contract_id: int, data: InvoiceCreate) -> Invoice:
    contract = get_contract(db, contract_id)
    room = _lock_room(db, contract.room_id)
    contract = db.scalar(select(Contract).where(Contract.id == contract_id).with_for_update().execution_options(populate_existing=True))
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if contract.status != "active":
        raise HTTPException(status_code=409, detail="Chỉ sinh hóa đơn cho hợp đồng đang hoạt động.")
    year, month = map(int, data.period.split("-"))
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    if contract.start_date > last or contract.end_date < first:
        raise HTTPException(status_code=409, detail="Hợp đồng không có hiệu lực trong tháng này.")
    if _invoice_for_room_period(db, room.id, data.period):
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
    contract = db.get(Contract, invoice.contract_id)
    _lock_room(db, contract.room_id)
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update().execution_options(populate_existing=True))
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="Hóa đơn đã được thanh toán đủ.")
    payments = db.scalars(select(Payment).where(Payment.invoice_id == invoice.id).with_for_update()).all()
    remaining = invoice.total_amount - sum(payment.amount for payment in payments)
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
