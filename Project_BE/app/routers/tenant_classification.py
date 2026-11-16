from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.tenant_classification import (
    ClassifiedTenant, TenantGroupResponse, TenantMemberCreate,
)
from app.services import tenant_classification as service

router = APIRouter(
    prefix="/api/contracts", tags=["Tenant classification (US-12)"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("/{contract_id}/tenant-group", response_model=TenantGroupResponse)
def read_group(
    contract_id: int = Path(gt=0), db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return service.list_group(db, user, contract_id)


@router.post("/{contract_id}/members", response_model=ClassifiedTenant,
             status_code=status.HTTP_201_CREATED)
def create_member(
    data: TenantMemberCreate, contract_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return service.add_member(db, user, contract_id, data.tenant_id)


@router.delete("/{contract_id}/members/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    contract_id: int = Path(gt=0), tenant_id: int = Path(gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    service.remove_member(db, user, contract_id, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
