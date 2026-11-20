import calendar
import hashlib
import json
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, select, insert, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.reading_revision import reading_revision
from app.db.invoice_snapshot import invoice_snapshot
from app.models.boarding import (
    Contract,
    Invoice,
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


def _utility_breakdown(db: Session, contract: Contract, period: str, prop):
    readings = {row.utility_type: row for row in db.scalars(select(UtilityReading).where(
        UtilityReading.room_id == contract.room_id, UtilityReading.period == period
    ).with_for_update())}
    services = get_effective_services(db, contract)
    lines = []
    def add(code, quantity, price, source, unit, reading=None):
        lines.append({'code':code, 'quantity':quantity, 'unit_price':price, 'amount':quantity*price,
                      'source':source, 'unit':unit, 'reading_id':reading.id if reading else None,
                      'previous_reading':reading.previous_reading if reading else None,
                      'current_reading':reading.current_reading if reading else None})
    if not services:
        for code, column in PRICES.items():
            reading = readings.get(code)
            if reading is not None:
                add(code, reading.current_reading - reading.previous_reading, getattr(prop, column), 'property', None, reading)
        return lines, readings
    for service in services:
        if service.effective_price is None or service.billing_unit is None:
            raise HTTPException(status_code=409, detail=f"Chưa cấu hình giá/đơn vị cho {service.service_name}.")
        quantity = service.quantity
        if service.billing_unit.value in {"kwh", "m3"}:
            reading = readings.get(service.service_code.value)
            if reading is None:
                raise HTTPException(status_code=409, detail=f"Thiếu chỉ số {service.service_name} kỳ {period}.")
            quantity = reading.current_reading - reading.previous_reading
        add(service.service_code.value, quantity, service.effective_price, service.source, service.billing_unit.value, readings.get(service.service_code.value) if service.billing_unit.value in {'kwh','m3'} else None)
    assigned = {service.service_code.value for service in services}
    for code in ("electricity", "water"):
        if code not in assigned and (reading := readings.get(code)) is not None:
            add(code, reading.current_reading - reading.previous_reading, getattr(prop, PRICES[code]), 'property', None, reading)
    return lines, readings


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
    # Approval requests are not yet consumable by the ordinary monthly invoice
    # workflow; never silently issue using today's prices for the final period.
    from app.services import settlement_trial
    if settlement_trial.allowed(db):
        from app.db.settlement_trial import final_approvals
        request=db.execute(select(final_approvals.c.id).where(final_approvals.c.contract_id==contract.id,final_approvals.c.period==data.period).limit(1).with_for_update()).first()
        if request:
            raise HTTPException(409, 'Kỳ có yêu cầu cuối kỳ; chưa có quy trình phát hành/điều chỉnh được duyệt.')
    lines, readings = _utility_breakdown(db, contract, data.period, prop)
    utility_amount = sum(line['amount'] for line in lines)
    if contract.monthly_rent + utility_amount > 2_147_483_647:
        raise HTTPException(status_code=422, detail="Tổng tiền vượt giới hạn lưu trữ.")
    db.add(InvoiceMonth(room_id=room.id, period=data.period))
    invoice = Invoice(
        contract_id=contract.id, period=data.period, rent_amount=contract.monthly_rent,
        utility_amount=utility_amount, total_amount=contract.monthly_rent + utility_amount, status="unpaid",
    )
    db.add(invoice)
    db.flush()
    document = {'version':1,'invoice_id':invoice.id,'contract_id':contract.id,'room_id':room.id,
                'period':data.period,'period_start':first.isoformat(),'period_end':last.isoformat(),
                'contract_coverage_start':max(first,contract.start_date).isoformat(),
                'contract_coverage_end':min(last,contract.end_date).isoformat(),
                'rent_amount':invoice.rent_amount,'utility_amount':utility_amount,
                'lines':[{'code':'rent','quantity':1,'unit_price':invoice.rent_amount,'amount':invoice.rent_amount,'source':'contract','unit':'month'}]+lines,
                'readings':{kind: {'id':reading.id,'previous':reading.previous_reading,'current':reading.current_reading} for kind,reading in readings.items()},
                'missing_readings':[kind for kind in ('electricity','water') if kind not in readings],
                'adjustments':[], 'total_amount':invoice.total_amount,
                'issued_at':(invoice.created_at or datetime.now()).isoformat(), 'issued_by':user.id,'issued_status':'unpaid'}
    payload=json.dumps(document,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    db.execute(insert(invoice_snapshot).values(invoice_id=invoice.id,payload=payload,sha256=hashlib.sha256(payload.encode('utf-8')).hexdigest()))
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

    invoices = [
        item for item in db.scalars(query)
        if can_view_invoice(db, user, item)
    ]

    _attach_invoice_details(db, invoices)

    return invoices


def read_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)

    _attach_invoice_details(db, [invoice])

    return invoice

def read_invoice_snapshot(db: Session, user: User, invoice_id: int) -> dict:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)
    try:
        row = db.execute(select(invoice_snapshot).where(invoice_snapshot.c.invoice_id == invoice_id)).mappings().first()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(503, 'Chưa có migration chứng từ hóa đơn.') from exc
    if not row:
        return {'invoice_id':invoice_id, 'status':'manual_review_required', 'document':None}
    if hashlib.sha256(row['payload'].encode('utf-8')).hexdigest() != row['sha256']:
        return {'invoice_id':invoice_id, 'status':'integrity_error', 'document':None}
    try:
        document=json.loads(row['payload'])
        valid=(document.get('invoice_id')==invoice.id and document.get('contract_id')==invoice.contract_id
               and document.get('period')==invoice.period and document.get('total_amount')==invoice.total_amount
               and sum(line['amount'] for line in document.get('lines',[]))==invoice.total_amount)
    except (ValueError,TypeError,KeyError,AttributeError):
        return {'invoice_id':invoice_id, 'status':'integrity_error', 'document':None}
    return {'invoice_id':invoice_id, 'status':('complete' if valid and not document.get('missing_readings') else 'manual_review_required'), 'document':document}


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

def record_payment(
    db: Session,
    user: User,
    invoice_id: int,
    data: PaymentCreate,
) -> dict:
    invoice = get_invoice(db, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = _lock_room(db, contract.room_id)
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
