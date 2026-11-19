import calendar
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.boarding import (
    Contract,
    Invoice,
    InvoiceItem,
    InvoiceMonth,
    Payment,
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


def create_reading(
    db: Session, user: User, room_id: int, data: ReadingCreate
) -> UtilityReading:
    room = get_room(db, room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    exists = db.scalar(
        select(UtilityReading).where(
            UtilityReading.room_id == room.id,
            UtilityReading.utility_type == data.utility_type.value,
            UtilityReading.period == data.period,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Chỉ số kỳ này đã được ghi.")
    reading = UtilityReading(
        room_id=room.id,
        utility_type=data.utility_type.value,
        period=data.period,
        previous_reading=data.previous_reading,
        current_reading=data.current_reading,
        recorded_by=user.id,
    )
    db.add(reading)
    save(db, reading)
    return reading


def list_readings(db: Session, user: User, room_id: int) -> list[UtilityReading]:
    room = get_room(db, room_id)
    assert_can_operate(db, user, property_of_room(db, room))
    return list(
        db.scalars(
            select(UtilityReading)
            .where(UtilityReading.room_id == room.id)
            .order_by(UtilityReading.id)
        )
    )


def _utility_line_items(
    db: Session, contract: Contract, period: str, prop
) -> list[dict]:
    readings = {
        row.utility_type: row
        for row in db.scalars(
            select(UtilityReading).where(
                UtilityReading.room_id == contract.room_id,
                UtilityReading.period == period,
            )
        )
    }
    services = get_effective_services(db, contract)
    items: list[dict] = []
    if not services:
        names = {
            "electricity": ("Điện", "kWh"),
            "water": ("Nước", "m³"),
            "service": ("Dịch vụ", "đơn vị"),
        }
        for code, column in PRICES.items():
            reading = readings.get(code)
            if reading is not None:
                quantity = reading.current_reading - reading.previous_reading
                price = getattr(prop, column)
                items.append(
                    {
                        "description": names[code][0],
                        "quantity": quantity,
                        "unit": names[code][1],
                        "unit_price": price,
                        "amount": quantity * price,
                    }
                )
        return items
    for service in services:
        if service.effective_price is None or service.billing_unit is None:
            raise HTTPException(
                status_code=409,
                detail=f"Chưa cấu hình giá/đơn vị cho {service.service_name}.",
            )
        quantity = service.quantity
        if service.billing_unit.value in {"kwh", "m3"}:
            reading = readings.get(service.service_code.value)
            if reading is None:
                raise HTTPException(
                    status_code=409,
                    detail=f"Thiếu chỉ số {service.service_name} kỳ {period}.",
                )
            quantity = reading.current_reading - reading.previous_reading
        items.append(
            {
                "description": service.service_name,
                "quantity": quantity,
                "unit": service.billing_unit.value,
                "unit_price": service.effective_price,
                "amount": quantity * service.effective_price,
            }
        )
    return items


def create_invoice(
    db: Session, user: User, contract_id: int, data: InvoiceCreate
) -> Invoice:
    contract = get_contract(db, contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    assert_can_operate(db, user, prop)
    if contract.status != "active":
        raise HTTPException(
            status_code=409, detail="Chỉ sinh hóa đơn cho hợp đồng đang hoạt động."
        )
    year, month = map(int, data.period.split("-"))
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    if contract.start_date > last or contract.end_date < first:
        raise HTTPException(
            status_code=409, detail="Hợp đồng không có hiệu lực trong tháng này."
        )
    exists = db.scalar(
        select(Invoice)
        .join(Contract)
        .where(Contract.room_id == room.id, Invoice.period == data.period)
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Hóa đơn của kỳ này đã tồn tại.")
    utility_items = _utility_line_items(db, contract, data.period, prop)
    utility_amount = sum(item["amount"] for item in utility_items)
    if contract.monthly_rent + utility_amount > 2_147_483_647:
        raise HTTPException(status_code=422, detail="Tổng tiền vượt giới hạn lưu trữ.")
    db.add(InvoiceMonth(room_id=room.id, period=data.period))
    invoice = Invoice(
        contract_id=contract.id,
        period=data.period,
        rent_amount=contract.monthly_rent,
        utility_amount=utility_amount,
        total_amount=contract.monthly_rent + utility_amount,
        status="unpaid",
    )
    db.add(invoice)
    db.flush()
    invoice_items = [
        InvoiceItem(invoice_id=invoice.id, **item)
        for item in [
            {
                "description": "Tiền thuê phòng",
                "quantity": 1,
                "unit": "tháng",
                "unit_price": invoice.rent_amount,
                "amount": invoice.rent_amount,
            },
            *utility_items,
        ]
    ]
    db.add_all(invoice_items)
    save(db, invoice, *invoice_items)
    return invoice


def list_invoices(db: Session, user: User) -> list[Invoice]:
    return [
        item
        for item in db.scalars(select(Invoice).order_by(Invoice.id))
        if can_view_invoice(db, user, item)
    ]


def read_invoice(db: Session, user: User, invoice_id: int) -> Invoice:
    invoice = get_invoice(db, invoice_id)
    assert_can_view_invoice(db, user, invoice)
    return invoice


def invoice_details(db: Session, user: User, invoice_id: int) -> dict:
    invoice = read_invoice(db, user, invoice_id)
    contract = get_contract(db, invoice.contract_id)
    room = get_room(db, contract.room_id)
    prop = property_of_room(db, room)
    tenant = db.get(TenantProfile, contract.tenant_id)
    saved_items = list(
        db.scalars(
            select(InvoiceItem)
            .where(InvoiceItem.invoice_id == invoice.id)
            .order_by(InvoiceItem.id)
        )
    )
    if saved_items:
        items = [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "amount": item.amount,
            }
            for item in saved_items
        ]
    else:
        # Compatibility for invoices created before itemized snapshots were introduced.
        items = [
            {
                "description": "Tiền thuê phòng",
                "quantity": 1,
                "unit": "tháng",
                "unit_price": invoice.rent_amount,
                "amount": invoice.rent_amount,
            }
        ]
        items.extend(_utility_line_items(db, contract, invoice.period, prop))

    payments = list(
        db.scalars(
            select(Payment)
            .where(Payment.invoice_id == invoice.id)
            .order_by(Payment.paid_at, Payment.id)
        )
    )
    paid_amount = sum(payment.amount for payment in payments)
    return {
        "id": invoice.id,
        "contract_id": invoice.contract_id,
        "period": invoice.period,
        "rent_amount": invoice.rent_amount,
        "utility_amount": invoice.utility_amount,
        "total_amount": invoice.total_amount,
        "status": invoice.status,
        "tenant_name": tenant.full_name,
        "tenant_phone": tenant.phone,
        "tenant_email": tenant.email,
        "property_name": prop.name,
        "property_address": prop.address,
        "room_number": room.room_number,
        "line_items": items,
        "paid_amount": paid_amount,
        "remaining_amount": max(invoice.total_amount - paid_amount, 0),
        "payments": payments,
    }


def _paid_amount(db: Session, invoice_id: int) -> int:
    paid = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        )
    )
    return int(paid or 0)


def record_payment(
    db: Session, user: User, invoice_id: int, data: PaymentCreate
) -> Payment:
    invoice = read_invoice(db, user, invoice_id)
    if invoice.status == "paid":
        raise HTTPException(status_code=409, detail="Hóa đơn đã được thanh toán đủ.")
    remaining = invoice.total_amount - _paid_amount(db, invoice.id)
    if data.amount > remaining:
        raise HTTPException(
            status_code=409, detail="Số tiền thanh toán vượt quá số còn nợ."
        )
    payment = Payment(
        invoice_id=invoice.id,
        amount=data.amount,
        method=data.method.strip(),
        recorded_by=user.id,
    )
    db.add(payment)
    paid_after = remaining - data.amount
    invoice.status = "paid" if paid_after == 0 else "partially_paid"
    save(db, payment, invoice)
    return payment


def list_own_invoices(db: Session, user: User) -> list[Invoice]:
    return list(
        db.scalars(
            select(Invoice)
            .join(Contract, Contract.id == Invoice.contract_id)
            .join(TenantProfile, TenantProfile.id == Contract.tenant_id)
            .where(TenantProfile.user_id == user.id)
            .order_by(Invoice.id)
        )
    )
