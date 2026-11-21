from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import (
    InvoiceResponse,
    InvoiceDueDateUpdate,
    PaymentCreate,
    PaymentResult,
    PaymentHistoryResponse,
    ReadingCreate,
    ReadingResponse,
)
from app.services import billing_service

invoice_router = APIRouter(
    prefix="/api/invoices",
    tags=["Invoices"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)
reading_router = APIRouter(
    prefix="/api/rooms",
    tags=["Utilities"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@invoice_router.get("", response_model=list[InvoiceResponse])
def read_invoices(
    status_filter: str | None = Query(default=None, alias="status"),
    period: str | None = None,
    contract_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_READ)),
):
    return billing_service.list_invoices(
        db,
        user,
        status=status_filter,
        period=period,
        contract_id=contract_id,
    )


@invoice_router.get("/{invoice_id}", response_model=InvoiceResponse)
def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_READ)),
):
    return billing_service.read_invoice(db, user, invoice_id)

@invoice_router.post('/{invoice_id}/reconcile-status')
def reconcile_status(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.INVOICE_MANAGE))):
    return billing_service.reconcile_invoice_status(db,user,invoice_id)


@invoice_router.put('/{invoice_id}/due-date')
def set_due_date(invoice_id: int, data: InvoiceDueDateUpdate, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.INVOICE_MANAGE))):
    return billing_service.update_due_date(db, user, invoice_id, data)


@invoice_router.post(
    "/{invoice_id}/payments",
    response_model=PaymentResult,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    invoice_id: int,
    data: PaymentCreate,
    idempotency_key: str | None = Header(default=None, alias='Idempotency-Key', min_length=1, max_length=128, pattern=r'^[A-Za-z0-9._:-]+$'),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_MANAGE)),
):
    return billing_service.record_payment(db, user, invoice_id, data, idempotency_key)


@invoice_router.get(
    "/{invoice_id}/payments",
    response_model=list[PaymentHistoryResponse],
)
def read_payments(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_READ)),
):
    return billing_service.list_payments(db, user, invoice_id)

@reading_router.get("/{room_id}/readings", response_model=list[ReadingResponse])
def read_readings(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return billing_service.list_readings(db, user, room_id)


@reading_router.post("/{room_id}/readings", response_model=ReadingResponse, status_code=status.HTTP_201_CREATED)
def create_reading(
    room_id: int,
    data: ReadingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return billing_service.create_reading(db, user, room_id, data)
