from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.boarding import ContractResponse, InvoiceResponse
from app.schemas.user import PasswordChange, ProfileUpdate, RoleAssign, RoleChangeResponse, UserListResponse, UserResponse
from app.services.billing_service import list_own_invoices
from app.services.contract_service import list_own_contracts
from app.services.user_service import assign_role, change_password, get_account, list_users, update_profile

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


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def update_my_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROFILE_UPDATE)),
):
    change_password(db, user, data)


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


@router.get("", response_model=UserListResponse)
def read_users(
    q: str | None = Query(default=None, max_length=100),
    role: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permissions(Permission.USERS_READ)),
):
    return list_users(db, q=q, role=role, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permissions(Permission.PROFILE_READ)),
):
    return get_account(db, actor, user_id)


@router.put("/{user_id}/role", response_model=RoleChangeResponse)
def update_role(
    user_id: int,
    data: RoleAssign,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permissions(Permission.USERS_ASSIGN_ROLE)),
):
    target, revoked = assign_role(db, user_id, data.role.value, actor)
    response = RoleChangeResponse.model_validate(target)
    response.revoked_property_count = revoked
    return response
