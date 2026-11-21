from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.database import Base,get_db
from app.main import app
from app.models.user import User
from app.models.boarding import Property,PropertyManager,Room,TenantProfile,Contract,Invoice,Payment
from app.core.security import create_access_token

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);Base.metadata.create_all(engine);Session=sessionmaker(engine,expire_on_commit=False)
    with Session.begin() as db:
        users=[User(full_name=x,email=x+'@example.com',role=role,password_hash='x') for x,role in [('owner','landlord'),('other','landlord'),('manager','manager'),('tenant','tenant'),('admin','admin')]];db.add_all(users);db.flush()
        a=Property(owner_id=users[0].id,name='A',address='A');b=Property(owner_id=users[1].id,name='B',address='B');db.add_all([a,b]);db.flush()
        db.add(PropertyManager(property_id=a.id,user_id=users[2].id));r=Room(property_id=a.id,room_number='1',base_rent=100,status='occupied');db.add_all([r,Room(property_id=a.id,room_number='2',base_rent=100,status='available'),Room(property_id=a.id,room_number='3',base_rent=100,status='maintenance'),Room(property_id=b.id,room_number='4',base_rent=100,status='available')]);db.flush()
        tenant=TenantProfile(landlord_id=users[0].id,created_by=users[0].id,full_name='T',phone='0900000000',id_number='123456789012');db.add(tenant);db.flush()
        contract=Contract(room_id=r.id,tenant_id=tenant.id,created_by=users[0].id,start_date=date.today()-timedelta(days=30),end_date=date.today()+timedelta(days=30),monthly_rent=100,deposit=0,status='active');db.add(contract);db.flush()
        invoice=Invoice(contract_id=contract.id,period=date.today().strftime('%Y-%m'),rent_amount=100,utility_amount=0,total_amount=100,status='unpaid');db.add(invoice);db.flush();iid,pid=invoice.id,a.id;headers=[{'Authorization':'Bearer '+create_access_token(u.id)} for u in users]
    def dep():
        with Session() as db: yield db
    app.dependency_overrides[get_db]=dep
    yield TestClient(app),headers,iid,pid
    app.dependency_overrides.clear();engine.dispose()

def test_dashboard_scope_and_payment(env):
    c,(h,other,manager,tenant,admin),iid,pid=env
    assert c.get('/api/dashboard/summary',headers=tenant).status_code==403
    assert c.get('/api/dashboard/summary',headers=admin).status_code==403
    d=c.get('/api/dashboard/summary',headers=h).json();assert (d['total_rooms'],d['available_rooms'],d['occupied_rooms'],d['maintenance_rooms'],d['outstanding'])==(3,1,1,1,100)
    assert c.get('/api/dashboard/summary',headers=manager).json()['total_rooms']==3
    assert c.get(f'/api/dashboard/summary?property_id={pid}',headers=other).status_code==403
    assert c.post(f'/api/invoices/{iid}/payments',headers=h,json={'amount':30,'method':'cash'}).status_code==201
    d=c.get('/api/dashboard/summary',headers=h).json();assert d['outstanding']==70 and d['revenue_received']==30 and d['invoiced_amount']==100
    assert c.get('/api/dashboard/summary?period=0000-01',headers=h).status_code==422
    assert c.get('/api/dashboard/summary?period=2000-01',headers=h).json()['revenue_received']==0

def test_status_reconciliation_and_payment_scope(env):
    c,(h,other,manager,tenant,admin),iid,_=env;url=f'/api/invoices/{iid}/reconcile-status'
    assert c.post(url,headers=tenant).status_code==403
    assert c.post(url,headers=other).status_code==403
    assert c.post('/api/invoices/99999/reconcile-status',headers=h).status_code==404
    assert c.post(url,headers=h).json()['status']=='unpaid'
    assert c.post(f'/api/invoices/{iid}/payments',headers=manager,json={'amount':30,'method':'cash'}).json()['invoice_status']=='partially_paid'
    assert c.post(url,headers=h).json()['status']=='partially_paid'
    assert c.post(f'/api/invoices/{iid}/payments',headers=h,json={'amount':71,'method':'cash'}).status_code==409
    assert c.post(f'/api/invoices/{iid}/payments',headers=h,json={'amount':70,'method':'cash'}).json()['invoice_status']=='paid'
    assert c.post(url,headers=h).json()['status']=='paid'
    assert len(c.get(f'/api/invoices/{iid}/payments',headers=h).json())==2


def test_due_date_authorization_audit_and_effective_status(env):
    from app.models.boarding import InvoiceDueDateHistory
    from sqlalchemy import select
    c,(h,other,manager,tenant,admin),iid,_=env
    url=f'/api/invoices/{iid}/due-date'
    yesterday=(date.today()-timedelta(days=1)).isoformat()
    payload={'due_date':yesterday,'reason':'Contract clause 3'}
    assert c.put(url,headers=tenant,json=payload).status_code==403
    assert c.put(url,headers=other,json=payload).status_code==403
    assert c.put(url,headers=h,json={'due_date':yesterday,'reason':'  '}).status_code==422
    assert c.put(url,headers=manager,json=payload).json()['effective_status']=='overdue'
    assert c.put(url,headers=manager,json=payload).status_code==200
    inv=c.get(f'/api/invoices/{iid}',headers=h).json()
    assert inv['status']=='unpaid' and inv['effective_status']=='overdue' and inv['remaining_amount']==100
    assert c.post(f'/api/invoices/{iid}/payments',headers=h,json={'amount':40,'method':'cash'}).json()['effective_status']=='overdue'
    inv=c.get(f'/api/invoices/{iid}',headers=h).json()
    assert inv['paid_amount']==40 and inv['remaining_amount']==60 and inv['effective_status']=='overdue'
    assert len(c.get('/api/invoices?status=overdue',headers=h).json())==1
    assert c.post(f'/api/invoices/{iid}/payments',headers=h,json={'amount':60,'method':'cash'}).json()['effective_status']=='paid'
    dep=app.dependency_overrides[get_db]()
    db=next(dep)
    assert len(db.scalars(select(InvoiceDueDateHistory)).all())==1
    dep.close()


def test_vietnam_date_boundaries():
    from datetime import datetime,timezone
    from app.services.billing_service import effective_status
    due=date(2026,1,31)
    assert effective_status(100,0,None,datetime(2026,2,1,tzinfo=timezone.utc))=='unpaid'
    assert effective_status(100,20,due,datetime(2026,1,31,16,59,tzinfo=timezone.utc))=='partially_paid'
    assert effective_status(100,20,due,datetime(2026,1,31,17,0,tzinfo=timezone.utc))=='overdue'
    assert effective_status(100,100,due,datetime(2026,2,1,tzinfo=timezone.utc))=='paid'


def test_due_date_commit_failure_rolls_back(env, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session
    from app.models.boarding import InvoiceDueDateHistory
    from sqlalchemy import select
    c,(h,*_),iid,_=env
    def fail_commit(self):
        raise SQLAlchemyError('simulated failure')
    with monkeypatch.context() as m:
        m.setattr(Session,'commit',fail_commit)
        result=c.put(f'/api/invoices/{iid}/due-date',headers=h,json={'due_date':'2026-01-01','reason':'contract'})
        assert result.status_code==503
    assert c.get(f'/api/invoices/{iid}',headers=h).json()['due_date'] is None
    dep=app.dependency_overrides[get_db](); db=next(dep)
    assert not db.scalars(select(InvoiceDueDateHistory)).all()
    dep.close()


def test_invoice_contract_filter_cannot_expose_another_property(env):
    from sqlalchemy import select
    c,(owner,other,*_),iid,_=env
    dep=app.dependency_overrides[get_db]();db=next(dep)
    other_user=db.scalar(select(User).where(User.email=='other@example.com'))
    room=db.scalar(select(Room).where(Room.room_number=='4'))
    tenant=TenantProfile(landlord_id=other_user.id,created_by=other_user.id,full_name='Other',phone='0900000001',id_number='123456789013')
    db.add(tenant);db.flush()
    contract=Contract(room_id=room.id,tenant_id=tenant.id,created_by=other_user.id,start_date=date.today(),end_date=date.today()+timedelta(days=30),monthly_rent=100,deposit=0,status='active')
    db.add(contract);db.flush()
    db.add(Invoice(contract_id=contract.id,period='2020-01',rent_amount=100,utility_amount=0,total_amount=100,status='unpaid'));db.commit();other_contract=contract.id
    dep.close()
    assert c.get(f'/api/invoices?contract_id={other_contract}',headers=owner).json()==[]
    result=c.get(f'/api/invoices?contract_id={other_contract}',headers=other).json()
    assert len(result)==1 and result[0]['contract_id']==other_contract
