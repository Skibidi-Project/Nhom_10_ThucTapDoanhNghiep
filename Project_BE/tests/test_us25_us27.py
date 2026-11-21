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


def test_us21_reading_history_scope_and_periods(env):
    from sqlalchemy import select
    c,(owner,other,manager,tenant,_),_,_=env
    dep=app.dependency_overrides[get_db]();db=next(dep)
    room_id=db.scalar(select(Room.id).where(Room.room_number=='1'));dep.close()
    for period,previous,current in [('2026-01',100,140),('2026-02',140,165)]:
        r=c.post(f'/api/rooms/{room_id}/readings',headers=owner,json={'utility_type':'electricity','period':period,'previous_reading':previous,'current_reading':current})
        assert r.status_code==201
    assert c.post(f'/api/rooms/{room_id}/readings',headers=owner,json={'utility_type':'electricity','period':'2026-02','previous_reading':140,'current_reading':165}).status_code==409
    readings=c.get(f'/api/rooms/{room_id}/readings',headers=manager).json()
    assert [(r['period'],r['current_reading']-r['previous_reading']) for r in readings]==[('2026-01',40),('2026-02',25)]
    assert c.get(f'/api/rooms/{room_id}/readings',headers=other).status_code==403
    assert c.get(f'/api/rooms/{room_id}/readings',headers=tenant).status_code==403


def test_us26_expense_crud_scope_validation_and_dashboard(env):
    c,(owner,other,manager,tenant,admin),_,pid=env
    payload={'property_id':pid,'category':'repair','description':'Repair','amount':120,'expense_date':date.today().isoformat()}
    assert c.post('/api/expenses',headers=tenant,json=payload).status_code==403
    assert c.post('/api/expenses',headers=admin,json=payload).status_code==403
    assert c.post('/api/expenses',headers=other,json=payload).status_code==403
    assert c.post('/api/expenses',headers=owner,json={**payload,'amount':0}).status_code==422
    assert c.post('/api/expenses',headers=owner,json={**payload,'expense_date':(date.today()+timedelta(days=1)).isoformat()}).status_code==422
    r=c.post('/api/expenses',headers=manager,json=payload);assert r.status_code==201
    eid=r.json()['id']
    assert c.get(f'/api/expenses/{eid}',headers=other).status_code==403
    assert c.get('/api/expenses/summary',headers=owner).json()['total_amount']==120
    assert c.get('/api/dashboard/summary',headers=owner).json()['expenses']==120
    assert c.put(f'/api/expenses/{eid}',headers=other,json={'amount':200}).status_code==403
    assert c.put(f'/api/expenses/{eid}',headers=owner,json={'amount':200}).json()['amount']==200
    assert c.get('/api/expenses',headers=manager).json()['total_amount']==200
    assert c.delete(f'/api/expenses/{eid}',headers=other).status_code==403
    assert c.delete(f'/api/expenses/{eid}',headers=owner).status_code==204
    assert c.get('/api/expenses/summary',headers=owner).json()['count']==0


def test_us20_existing_billing_price_source_difference(env):
    from sqlalchemy import select
    from app.models.boarding import PropertyServicePrice,UtilityReading
    from app.models.service_assignment import ServiceAssignment
    from app.services.billing_service import _utility_amount
    _,_,_,pid=env
    dep=app.dependency_overrides[get_db]();db=next(dep)
    prop=db.get(Property,pid);prop.electricity_unit_price=2
    contract=db.scalar(select(Contract));uid=contract.created_by
    db.add(PropertyServicePrice(property_id=pid,service_code='electricity',billing_unit='kwh',unit_price=3))
    db.add(ServiceAssignment(contract_id=contract.id,service_code='electricity',quantity=1,price_override=4,assigned_by=uid))
    db.add(UtilityReading(room_id=contract.room_id,utility_type='electricity',period='2026-01',previous_reading=10,current_reading=20,recorded_by=uid));db.commit()
    # The published US-20 branch uses the property field; main billing uses the contract override.
    assert (20-10)*prop.electricity_unit_price == 20
    assert _utility_amount(db,contract,'2026-01',prop)==40
    dep.close()


def test_register_login_expired_token_and_role_access(env):
    import secrets,jwt
    from datetime import datetime,timezone
    from app.core.security import _secret
    c,(owner,other,manager,tenant,admin),_,_=env
    password=secrets.token_urlsafe(18)
    body={'full_name':'New User','email':'newuser@example.com','phone':'0900000022','password':password}
    r=c.post('/api/auth/register',json=body);assert r.status_code==201
    assert c.post('/api/auth/register',json=body).status_code==409
    r=c.post('/api/auth/login',json={'identifier':body['email'],'password':password});assert r.status_code==200
    token=r.json()['access_token'];assert c.get('/api/users/me',headers={'Authorization':'Bearer '+token}).status_code==200
    expired=jwt.encode({'sub':str(r.json()['user']['id']),'exp':datetime.now(timezone.utc)-timedelta(minutes=1)},_secret(),algorithm='HS256')
    assert c.get('/api/users/me',headers={'Authorization':'Bearer '+expired}).status_code==401
    assert c.get('/api/users/me').status_code==401
    assert c.get('/api/properties',headers=tenant).status_code==403
    assert c.get('/api/properties',headers=admin).status_code==403
    assert c.get('/api/properties',headers=manager).status_code==200


def test_us22_invoice_creation_utilities_duplicate_and_scope(env):
    from sqlalchemy import select
    from app.models.boarding import UtilityReading
    c,(owner,other,manager,tenant,_),_,pid=env
    dep=app.dependency_overrides[get_db]();db=next(dep)
    prop=db.get(Property,pid);prop.electricity_unit_price=2;prop.water_unit_price=3
    contract=db.scalar(select(Contract));period=(date.today().replace(day=1)-timedelta(days=1)).strftime('%Y-%m')
    for kind,old,new in [('electricity',10,20),('water',5,10)]:
        db.add(UtilityReading(room_id=contract.room_id,utility_type=kind,period=period,previous_reading=old,current_reading=new,recorded_by=contract.created_by))
    db.commit();cid=contract.id;dep.close()
    url=f'/api/contracts/{cid}/invoices'
    assert c.post(url,headers=tenant,json={'period':period}).status_code==403
    assert c.post(url,headers=other,json={'period':period}).status_code==403
    result=c.post(url,headers=manager,json={'period':period});assert result.status_code==201
    assert result.json()['rent_amount']==100 and result.json()['utility_amount']==35 and result.json()['total_amount']==135
    assert c.post(url,headers=owner,json={'period':period}).status_code==409


def test_payment_idempotency_replay_conflict_and_authorization(env):
    c,(owner,other,manager,tenant,_),iid,_=env
    url=f'/api/invoices/{iid}/payments'
    headers={**owner,'Idempotency-Key':'attempt-001'}
    body={'amount':30,'method':'cash'}
    first=c.post(url,headers=headers,json=body);assert first.status_code==201
    assert c.post(url,headers={**other,'Idempotency-Key':'attempt-001'},json=body).status_code==403
    assert c.post(url,headers={**tenant,'Idempotency-Key':'attempt-001'},json=body).status_code==403
    replay=c.post(url,headers=headers,json=body);assert replay.status_code==201 and replay.json()['id']==first.json()['id']
    assert c.post(url,headers=headers,json={'amount':31,'method':'cash'}).status_code==409
    assert c.post(url,headers=owner,json={'amount':70,'method':'cash'}).status_code==201
    replay=c.post(url,headers=headers,json=body);assert replay.status_code==201 and replay.json()['remaining_amount']==0
    assert len(c.get(url,headers=owner).json())==2
    assert c.post(url,headers={**owner,'Idempotency-Key':'bad key'},json=body).status_code==422


def test_billing_existing_price_paths_and_assignment_precedence(env):
    from sqlalchemy import select
    from app.models.boarding import PropertyServicePrice,UtilityReading
    from app.models.service_assignment import ServiceAssignment
    from app.services.billing_service import _utility_amount
    from fastapi import HTTPException
    _,_,_,pid=env
    dep=app.dependency_overrides[get_db]();db=next(dep)
    prop=db.get(Property,pid);prop.electricity_unit_price=2
    contract=db.scalar(select(Contract));uid=contract.created_by
    db.add(UtilityReading(room_id=contract.room_id,utility_type='electricity',period='2026-01',previous_reading=10,current_reading=20,recorded_by=uid));db.flush()
    assert _utility_amount(db,contract,'2026-01',prop)==20
    room_assignment=ServiceAssignment(room_id=contract.room_id,service_code='electricity',quantity=1,assigned_by=uid)
    db.add(room_assignment);db.flush()
    with pytest.raises(HTTPException) as exc:_utility_amount(db,contract,'2026-01',prop)
    assert exc.value.status_code==409
    db.add(PropertyServicePrice(property_id=pid,service_code='electricity',billing_unit='kwh',unit_price=3));db.flush()
    assert _utility_amount(db,contract,'2026-01',prop)==30
    room_assignment.price_override=4;db.flush()
    assert _utility_amount(db,contract,'2026-01',prop)==40
    db.add(ServiceAssignment(contract_id=contract.id,service_code='electricity',quantity=1,price_override=5,assigned_by=uid));db.flush()
    assert _utility_amount(db,contract,'2026-01',prop)==50
    dep.close()
