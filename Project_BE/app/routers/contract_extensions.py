from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import ContractExtend, ContractExtensionResponse, ContractResponse
from app.services import contract_extension_service

router = APIRouter(
    prefix="/api/contracts",
    tags=["Contract Extensions"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.post("/{contract_id}/extend", response_model=ContractResponse)
def extend_contract(
    contract_id: int,
    data: ContractExtend,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_extension_service.extend_contract(db, user, contract_id, data)


@router.get("/{contract_id}/extensions", response_model=list[ContractExtensionResponse])
def list_contract_extensions(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.CONTRACT_MANAGE)),
):
    return contract_extension_service.list_extensions(db, user, contract_id)
