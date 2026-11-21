from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from app.core.deps import block_privilege_override, get_current_user, require_permissions
from app.core.rbac import Permission
from app.db.database import get_db
from app.models.user import User
from app.models.boarding import Property, PropertyManager, Room, Contract, Invoice, Payment
from app.models.expense import Expense

router=APIRouter(prefix='/api/dashboard',tags=['Dashboard'],dependencies=[Depends(get_current_user),Depends(block_privilege_override)])

@router.get('/summary')
def summary(period: str | None = Query(default=None,pattern=r'^\d{4}-(0[1-9]|1[0-2])$'), property_id: int | None = Query(default=None,gt=0),db: Session = Depends(get_db),user: User = Depends(require_permissions(Permission.PROPERTY_OPERATE))):
    period=period or date.today().strftime('%Y-%m')
    try: first=date.fromisoformat(period+'-01')
    except ValueError: raise HTTPException(422,'Kỳ không hợp lệ.')
    if first.year==9999 and first.month==12: raise HTTPException(422,'Kỳ không hợp lệ.')
    next_month=date(first.year+(first.month==12),first.month%12+1,1)
    scope=select(Property.id)
    if user.role=='landlord': scope=scope.where(Property.owner_id==user.id)
    elif user.role=='manager': scope=scope.join(PropertyManager,PropertyManager.property_id==Property.id).where(PropertyManager.user_id==user.id)
    else: raise HTTPException(403,'Không có quyền xem dashboard.')
    if property_id is not None:
        if db.scalar(scope.where(Property.id==property_id)) is None: raise HTTPException(403,'Không có quyền xem khu trọ.')
        scope=scope.where(Property.id==property_id)
    prop_count=db.scalar(select(func.count()).select_from(scope.subquery())) or 0
    room_counts=dict(db.execute(select(Room.status,func.count()).where(Room.property_id.in_(scope)).group_by(Room.status)).all())
    total=sum(room_counts.values()); occupied=room_counts.get('occupied',0); vacant=room_counts.get('available',0)
    paid=select(Payment.invoice_id.label('invoice_id'),func.sum(Payment.amount).label('amount')).group_by(Payment.invoice_id).subquery()
    invoice_scope=(select(Invoice.total_amount,func.coalesce(paid.c.amount,0).label('paid')).join(Contract,Contract.id==Invoice.contract_id).join(Room,Room.id==Contract.room_id).outerjoin(paid,paid.c.invoice_id==Invoice.id).where(Room.property_id.in_(scope),Invoice.period==period)).subquery()
    invoice_total,invoice_paid,count,outstanding,overpaid=db.execute(select(func.coalesce(func.sum(invoice_scope.c.total_amount),0),func.coalesce(func.sum(invoice_scope.c.paid),0),func.count(),func.coalesce(func.sum(case((invoice_scope.c.total_amount>invoice_scope.c.paid,invoice_scope.c.total_amount-invoice_scope.c.paid),else_=0)),0),func.coalesce(func.sum(case((invoice_scope.c.paid>invoice_scope.c.total_amount,1),else_=0)),0)).select_from(invoice_scope)).one()
    revenue=db.scalar(select(func.coalesce(func.sum(Payment.amount),0)).join(Invoice,Invoice.id==Payment.invoice_id).join(Contract,Contract.id==Invoice.contract_id).join(Room,Room.id==Contract.room_id).where(Room.property_id.in_(scope),Payment.paid_at>=datetime.combine(first,datetime.min.time()),Payment.paid_at<datetime.combine(next_month,datetime.min.time()))) or 0
    expense=db.scalar(select(func.coalesce(func.sum(Expense.amount),0)).where(Expense.property_id.in_(scope),Expense.expense_date>=first,Expense.expense_date<next_month)) or 0
    return {'period':period,'property_count':prop_count,'total_rooms':total,'occupied_rooms':occupied,'available_rooms':vacant,'maintenance_rooms':room_counts.get('maintenance',0),'other_rooms':total-occupied-vacant-room_counts.get('maintenance',0),'occupancy_percent':round(100*occupied/total,2) if total else 0,'invoice_count':count,'invoiced_amount':int(invoice_total),'invoice_period_paid':int(invoice_paid),'outstanding':int(outstanding),'overpaid_invoice_count':int(overpaid),'revenue_received':int(revenue),'expenses':int(expense)}
