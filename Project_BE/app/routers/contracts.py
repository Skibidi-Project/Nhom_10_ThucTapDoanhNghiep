from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import ContractCreate, ContractResponse, InvoiceCreate, InvoiceResponse
from app.services import billing_service, contract_service

router = APIRouter(
    prefix="/api/contracts",
    tags=["Contracts"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("", response_model=list[ContractResponse])
def read_contracts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_service.list_contracts(db, user)


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    data: ContractCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_service.create_contract(db, user, data)


@router.get("/{contract_id}", response_model=ContractResponse)
def read_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_service.read_contract(db, user, contract_id)


@router.post("/{contract_id}/terminate", response_model=ContractResponse)
def terminate_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_service.terminate_contract(db, user, contract_id)


@router.post("/{contract_id}/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    contract_id: int,
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_MANAGE)),
):
    return billing_service.create_invoice(db, user, contract_id, data)
