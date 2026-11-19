from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import ContractResponse, InvoiceResponse
from app.schemas.user import ProfileUpdate, RoleAssign, UserResponse
from app.services.billing_service import list_own_invoices
from app.services.contract_service import list_own_contracts
from app.services.user_service import assign_role, get_account, list_users, update_profile

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(require_permissions(Permission.PROFILE_READ))):
    return user


@router.put("/me", response_model=UserResponse)
def update_me(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROFILE_UPDATE)),
):
    return update_profile(db, user, data)


@router.get("/me/contracts", response_model=list[ContractResponse])
def read_my_contracts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.RENTAL_READ_OWN)),
):
    return list_own_contracts(db, user)


@router.get("/me/invoices", response_model=list[InvoiceResponse])
def read_my_invoices(
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.RENTAL_READ_OWN)),
):
    return list_own_invoices(db, user)


@router.get("", response_model=list[UserResponse])
def read_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions(Permission.USERS_READ)),
):
    return list_users(db)


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permissions(Permission.PROFILE_READ)),
):
    return get_account(db, actor, user_id)


@router.put("/{user_id}/role", response_model=UserResponse)
def update_role(
    user_id: int,
    data: RoleAssign,
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions(Permission.USERS_ASSIGN_ROLE)),
):
    return assign_role(db, user_id, data.role.value)
