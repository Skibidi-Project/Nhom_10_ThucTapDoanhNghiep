from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import InvoiceResponse, PaymentCreate, PaymentResponse, ReadingCreate, ReadingResponse
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
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_READ)),
):
    return billing_service.list_invoices(db, user)


@invoice_router.get("/{invoice_id}", response_model=InvoiceResponse)
def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_READ)),
):
    return billing_service.read_invoice(db, user, invoice_id)


@invoice_router.post("/{invoice_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def create_payment(
    invoice_id: int,
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_MANAGE)),
):
    return billing_service.record_payment(db, user, invoice_id, data)


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
