from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import ContractCreate, ContractResponse, DepositUpdate, InvoiceCreate, InvoiceResponse
from app.services import billing_service, contract_service
from app.services.db_util import execute_write
from app.schemas.boarding import TrialHandover, TrialDamage, TrialRefund, TrialFinalApprovalCreate, TrialFinalApprovalDecision, TrialMeterHandover
from app.services import settlement_trial

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


@router.patch("/{contract_id}/deposit", response_model=ContractResponse)
def update_contract_deposit(
    contract_id: int,
    data: DepositUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_service.update_deposit(db, user, contract_id, data)


@router.post("/{contract_id}/liquidate", response_model=ContractResponse)
def liquidate_contract(
    contract_id: int,
    data: TrialHandover | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    if data is not None:
        execute_write(db, settlement_trial.handover, user, contract_id, data)
        return contract_service.read_contract(db, user, contract_id)
    return contract_service.liquidate_contract(db, user, contract_id)

@router.post('/{contract_id}/liquidation-damages')
def add_trial_damage(contract_id: int, data: TrialDamage, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.add_damage, user, contract_id, data)

@router.post('/{contract_id}/liquidation-damages/{damage_id}/confirm')
def confirm_trial_damage(contract_id: int, damage_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.confirm_damage, user, contract_id, damage_id)

@router.post('/{contract_id}/liquidation-refund')
def refund_trial(contract_id: int, data: TrialRefund, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.record_refund, user, contract_id, data)

@router.post('/{contract_id}/liquidation-invoices/{invoice_id}/review')
def review_trial_invoice(contract_id: int, invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.review_invoice, user, contract_id, invoice_id)

@router.post('/{contract_id}/final-approvals', status_code=201)
def create_final_approval(contract_id: int, data: TrialFinalApprovalCreate, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.create_final_approval, user, contract_id, data)

@router.post('/{contract_id}/final-meter-handover',status_code=201)
def confirm_final_meter(contract_id: int, data: TrialMeterHandover, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.confirm_meter_handover, user, contract_id, data)

@router.post('/{contract_id}/final-invoice',status_code=201)
def create_final_trial_invoice(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.issue_final_invoice, user, contract_id)

@router.get('/{contract_id}/final-approvals')
def list_final_approvals(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return settlement_trial.list_final_approvals(db, user, contract_id)

@router.post('/{contract_id}/final-approvals/{approval_id}/decision')
def decide_final_approval(contract_id: int, approval_id: int, data: TrialFinalApprovalDecision, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return execute_write(db, settlement_trial.decide_final_approval, user, contract_id, approval_id, data)


@router.get("/{contract_id}/liquidation-preview")
def liquidation_preview(contract_id: int, db: Session = Depends(get_db), user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE))):
    return contract_service.liquidation_preview(db, user, contract_id)


@router.post("/{contract_id}/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    contract_id: int,
    data: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.INVOICE_MANAGE)),
):
    return execute_write(db, billing_service.create_invoice, user, contract_id, data)
