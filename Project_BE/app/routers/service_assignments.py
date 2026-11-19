from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import (
    block_privilege_override,
    get_current_user,
    require_permissions,
)
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.service_assignment import (
    EffectiveServiceResponse,
    ServiceAssignmentResponse,
    ServiceAssignmentUpdate,
    ServiceAssignmentWrite,
)
from app.services import service_assignment_service

router = APIRouter(
    prefix="/api",
    tags=["Service assignments"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("/service-assignments", response_model=list[ServiceAssignmentResponse])
def list_assignments(
    room_id: int | None = Query(default=None, gt=0),
    contract_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return service_assignment_service.list_service_assignments(
        db, user, room_id=room_id, contract_id=contract_id
    )


@router.post(
    "/service-assignments",
    response_model=ServiceAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    data: ServiceAssignmentWrite,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return service_assignment_service.create_service_assignment(db, user, data)


@router.put(
    "/service-assignments/{assignment_id}", response_model=ServiceAssignmentResponse
)
def update_assignment(
    assignment_id: int,
    data: ServiceAssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return service_assignment_service.update_service_assignment(
        db, user, assignment_id, data
    )


@router.delete(
    "/service-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    service_assignment_service.delete_service_assignment(db, user, assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/contracts/{contract_id}/services", response_model=list[EffectiveServiceResponse]
)
def read_contract_services(
    contract_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.UTILITY_MANAGE)),
):
    return service_assignment_service.get_contract_service_list(db, user, contract_id)
