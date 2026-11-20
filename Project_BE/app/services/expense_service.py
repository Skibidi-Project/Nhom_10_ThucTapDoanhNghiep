from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import Role
from app.models.boarding import Property, PropertyManager, Room
from app.models.expense import Expense
from app.models.user import User
from app.schemas.expense import (
    CATEGORY_LABELS,
    ExpenseCreate,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseSummaryResponse,
    ExpenseUpdate,
)
from app.services.access_scope import assert_can_operate, get_property, get_room
from app.services.db_util import save


def _scope_stmt(stmt, db: Session, user: User):
    if user.role == Role.LANDLORD.value:
        return stmt.where(Property.owner_id == user.id)
    if user.role == Role.MANAGER.value:
        return (
            stmt.join(PropertyManager, PropertyManager.property_id == Expense.property_id)
            .where(PropertyManager.user_id == user.id)
        )
    raise HTTPException(status_code=403, detail="Trang này dành cho chủ nhà và quản lý.")


def _validate_property_room(db: Session, user: User, property_id: int, room_id: int | None):
    prop = get_property(db, property_id)
    assert_can_operate(db, user, prop)
    if room_id is not None:
        room = get_room(db, room_id)
        if room.property_id != property_id:
            raise HTTPException(status_code=422, detail="Phòng không thuộc khu trọ đã chọn.")
    if room_id is not None:
        return room
    return None


def _validate_date(expense_date: date) -> None:
    if expense_date > date.today():
        raise HTTPException(status_code=422, detail="Ngày chi không được ở tương lai.")


def _item(row) -> ExpenseItem:
    expense, property_name, room_number, creator_name = row
    category = expense.category
    return ExpenseItem(
        id=expense.id,
        property_id=expense.property_id,
        property_name=property_name,
        room_id=expense.room_id,
        room_number=room_number,
        category=category,
        category_label=CATEGORY_LABELS.get(category, category),
        description=expense.description,
        vendor=expense.vendor,
        amount=expense.amount,
        expense_date=expense.expense_date,
        created_by=expense.created_by,
        created_by_name=creator_name,
        created_at=expense.created_at,
    )


def _rows_stmt():
    return (
        select(Expense, Property.name, Room.room_number, User.full_name)
        .join(Property, Property.id == Expense.property_id)
        .outerjoin(Room, Room.id == Expense.room_id)
        .join(User, User.id == Expense.created_by)
    )


def create_expense(db: Session, user: User, data: ExpenseCreate) -> ExpenseItem:
    _validate_property_room(db, user, data.property_id, data.room_id)
    _validate_date(data.expense_date)
    expense = Expense(
        property_id=data.property_id,
        room_id=data.room_id,
        category=data.category.value,
        description=data.description,
        vendor=data.vendor or None,
        amount=data.amount,
        expense_date=data.expense_date,
        created_by=user.id,
    )
    db.add(expense)
    save(db, expense)
    row = db.execute(_rows_stmt().where(Expense.id == expense.id)).one()
    return _item(row)


def _base_filters(db: Session, user: User, property_id: int | None, room_id: int | None,
                  category: str | None, date_from: date | None, date_to: date | None, search: str | None):
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="Từ ngày không được sau đến ngày.")
    stmt = _rows_stmt()
    if user.role == Role.LANDLORD.value:
        stmt = stmt.where(Property.owner_id == user.id)
    elif user.role == Role.MANAGER.value:
        stmt = stmt.join(PropertyManager, PropertyManager.property_id == Property.id).where(PropertyManager.user_id == user.id)
    else:
        raise HTTPException(status_code=403, detail="Trang này dành cho chủ nhà và quản lý.")
    if property_id is not None:
        prop = get_property(db, property_id)
        assert_can_operate(db, user, prop)
        stmt = stmt.where(Expense.property_id == property_id)
    if room_id is not None:
        stmt = stmt.where(Expense.room_id == room_id)
    if category is not None:
        stmt = stmt.where(Expense.category == category)
    if date_from is not None:
        stmt = stmt.where(Expense.expense_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Expense.expense_date <= date_to)
    if search:
        escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        if escaped:
            stmt = stmt.where((Expense.description.like(f"%{escaped}%", escape="\\")) | (Expense.vendor.like(f"%{escaped}%", escape="\\")))
    return stmt


def list_expenses(db: Session, user: User, property_id: int | None, room_id: int | None,
                  category: str | None, date_from: date | None, date_to: date | None,
                  search: str | None, page: int, page_size: int) -> ExpenseListResponse:
    stmt = _base_filters(db, user, property_id, room_id, category, date_from, date_to, search)
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0
    subquery = stmt.with_only_columns(Expense.amount).order_by(None).subquery()
    amount_stmt = select(func.coalesce(func.sum(subquery.c.amount), 0))
    total_amount = db.scalar(amount_stmt) or 0
    rows = db.execute(stmt.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return ExpenseListResponse(items=[_item(row) for row in rows], total=total, page=page, page_size=page_size, total_amount=total_amount)


def summarize_expenses(db: Session, user: User, property_id: int | None = None,
                       date_from: date | None = None, date_to: date | None = None) -> ExpenseSummaryResponse:
    stmt = _base_filters(db, user, property_id, None, None, date_from, date_to, None)
    count = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    subquery = stmt.with_only_columns(Expense.amount).order_by(None).subquery()
    total = db.scalar(select(func.coalesce(func.sum(subquery.c.amount), 0))) or 0
    category_totals: dict[str, dict[str, int]] = {}
    for expense, _, _, _ in db.execute(stmt).all():
        summary = category_totals.setdefault(expense.category, {"total": 0, "count": 0})
        summary["total"] += expense.amount
        summary["count"] += 1
    category_rows = sorted(category_totals.items(), key=lambda item: (-item[1]["total"], item[0]))
    by_category = [
        {"category": code, "category_label": CATEGORY_LABELS[code], "total": values["total"], "count": values["count"]}
        for code, values in category_rows
    ]
    return ExpenseSummaryResponse(total_amount=int(total), count=count, by_category=by_category)


def get_expense(db: Session, user: User, expense_id: int) -> ExpenseItem:
    stmt = _rows_stmt().where(Expense.id == expense_id)
    row = db.execute(_scope_stmt(stmt, db, user)).first()
    if row is None:
        existing = db.get(Expense, expense_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi.")
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem khoản chi này.")
    return _item(row)


def update_expense(db: Session, user: User, expense_id: int, data: ExpenseUpdate) -> ExpenseItem:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi.")
    prop = get_property(db, expense.property_id)
    assert_can_operate(db, user, prop)
    room_id = expense.room_id if data.room_id is None and "room_id" not in data.model_fields_set else data.room_id
    _validate_property_room(db, user, expense.property_id, room_id)
    if data.expense_date is not None:
        _validate_date(data.expense_date)
    if data.category is not None:
        expense.category = data.category.value
    if "description" in data.model_fields_set:
        expense.description = data.description
    if "vendor" in data.model_fields_set:
        expense.vendor = data.vendor or None
    if data.amount is not None:
        expense.amount = data.amount
    if data.expense_date is not None:
        expense.expense_date = data.expense_date
    if "room_id" in data.model_fields_set:
        expense.room_id = data.room_id
    save(db, expense)
    return get_expense(db, user, expense_id)


def delete_expense(db: Session, user: User, expense_id: int) -> None:
    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy khoản chi.")
    prop = get_property(db, expense.property_id)
    assert_can_operate(db, user, prop)
    db.delete(expense)
    save(db)
