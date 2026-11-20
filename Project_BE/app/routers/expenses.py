from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseSummaryResponse,
    ExpenseUpdate,
)
from app.services import expense_service

router = APIRouter(
    prefix="/api/expenses",
    tags=["Expenses"],
    dependencies=[Depends(get_current_user), Depends(block_privilege_override)],
)


@router.get("/summary", response_model=ExpenseSummaryResponse)
def expense_summary(
    property_id: int | None = Query(default=None, gt=0),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return expense_service.summarize_expenses(db, user, property_id, date_from, date_to)


@router.post("", response_model=ExpenseItem, status_code=status.HTTP_201_CREATED)
def create_expense(data: ExpenseCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return expense_service.create_expense(db, user, data)


@router.get("", response_model=ExpenseListResponse)
def list_expenses(
    property_id: int | None = Query(default=None, gt=0),
    room_id: int | None = Query(default=None, gt=0),
    category: str | None = Query(default=None, pattern=r"^(repair|supplies|operations|cleaning|other)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = Query(default=None, max_length=50),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE)),
):
    return expense_service.list_expenses(db, user, property_id, room_id, category, date_from, date_to, search, page, page_size)


@router.get("/{expense_id}", response_model=ExpenseItem)
def read_expense(expense_id: int, db: Session = Depends(get_db),
                 user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return expense_service.get_expense(db, user, expense_id)


@router.put("/{expense_id}", response_model=ExpenseItem)
def update_expense(expense_id: int, data: ExpenseUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    return expense_service.update_expense(db, user, expense_id, data)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    expense_service.delete_expense(db, user, expense_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
