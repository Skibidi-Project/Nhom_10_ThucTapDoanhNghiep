from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import TenantCreate, TenantResponse, TenantUpdate
from app.services import tenant_service

router = APIRouter(
    prefix="/api/tenants",
    tags=["Tenants"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("", response_model=list[TenantResponse])
def read_tenants(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.list_tenants(db, user)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.create_tenant(db, user, data)


@router.get("/{tenant_id}", response_model=TenantResponse)
def read_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.read_tenant(db, user, tenant_id)


@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    return tenant_service.update_tenant(db, user, tenant_id, data)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.TENANT_MANAGE)),
):
    tenant_service.delete_tenant(db, user, tenant_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
