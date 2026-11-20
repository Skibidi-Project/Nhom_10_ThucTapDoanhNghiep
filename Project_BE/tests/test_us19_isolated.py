import os
os.environ['DATABASE_URL'] = 'sqlite://'
from datetime import date, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db.database import Base, get_db
from app.db.reading_revision import reading_revision
import app.models, app.models.room_type
from app.models.user import User
from app.models.boarding import Property, Room, TenantProfile, Contract
from app.core.security import create_access_token
from app.main import app as application

def test_invoice_snapshot_keeps_original_prices_and_rbac(env):
    c,h,tenant,rid,pid,cid=env;period=date.today().strftime('%Y-%m')
    for kind,value in [('electricity',5),('water',3)]:
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':value}).status_code==201
    bill=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period})
    assert bill.status_code==201,bill.text
    url=f'/api/invoices/{bill.json()["id"]}/snapshot'
    snapshot=c.get(url,headers=h);assert snapshot.status_code==200
    doc=snapshot.json()['document'];assert snapshot.json()['status']=='complete'
    assert doc['total_amount']==210 and sum(x['amount'] for x in doc['lines'])==210
    assert {x['code']:x['unit_price'] for x in doc['lines']}=={'rent':100,'electricity':10,'water':20}
    dep=application.dependency_overrides[get_db]();db=next(dep)
    try:
        prop=db.get(Property,pid);prop.electricity_unit_price=999;db.commit()
        outsider=User(full_name='Other',email='outsider-snapshot@example.com',role='landlord',password_hash='x');db.add(outsider);db.commit()
        other={'Authorization':'Bearer '+create_access_token(outsider.id)}
    finally:dep.close()
    assert c.get(url,headers=h).json()['document']==doc
    assert c.get(url,headers=other).status_code==403

def test_legacy_invoice_needs_review_but_payment_works(env):
    from app.models.boarding import Invoice
    c,h,_,_,_,cid=env;dep=application.dependency_overrides[get_db]();db=next(dep)
    try:
        invoice=Invoice(contract_id=cid,period='2025-01',rent_amount=100,utility_amount=0,total_amount=100,status='unpaid');db.add(invoice);db.commit();invoice_id=invoice.id
    finally:dep.close()
    assert c.get(f'/api/invoices/{invoice_id}/snapshot',headers=h).json()['status']=='manual_review_required'
    assert c.post(f'/api/invoices/{invoice_id}/payments',headers=h,json={'amount':100,'method':'cash'}).status_code==201

def test_invoice_snapshot_failure_rolls_back_invoice(env):
    from app.db.invoice_snapshot import invoice_snapshot
    from app.models.boarding import Invoice, InvoiceMonth
    c,h,_,_,_,cid=env;dep=application.dependency_overrides[get_db]();db=next(dep)
    try: invoice_snapshot.drop(db.get_bind())
    finally:dep.close()
    result=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':date.today().strftime('%Y-%m')})
    assert result.status_code==503
    dep=application.dependency_overrides[get_db]();db=next(dep)
    try: assert db.query(Invoice).count()==0 and db.query(InvoiceMonth).count()==0
    finally:dep.close()

def test_jwt_secret_required(monkeypatch):
    from app.core.security import create_access_token
    monkeypatch.delenv('JWT_SECRET', raising=False)
    with pytest.raises(RuntimeError): create_access_token(1)
    monkeypatch.setenv('JWT_SECRET', 'short')
    with pytest.raises(RuntimeError): create_access_token(1)

def test_us26_expense_scope_and_crud(env):
    c,owner,tenant,rid,pid,_=env
    dep=application.dependency_overrides[get_db]();db=next(dep)
    try:
        other=User(full_name='Other',email='other-expense@example.com',role='landlord',password_hash='x')
        db.add(other);db.commit();outsider={'Authorization':'Bearer '+create_access_token(other.id)}
    finally: dep.close()
    data={'property_id':pid,'room_id':rid,'category':'repair','description':'Sửa điện','amount':100,'expense_date':date.today().isoformat()}
    assert c.post('/api/expenses',headers=tenant,json=data).status_code==403
    assert c.post('/api/expenses',headers=outsider,json=data).status_code==403
    assert c.post('/api/expenses',headers=owner,json={**data,'amount':-1}).status_code==422
    result=c.post('/api/expenses',headers=owner,json=data);assert result.status_code==201,result.text
    expense_id=result.json()['id'];url=f'/api/expenses/{expense_id}'
    assert c.get(url,headers=outsider).status_code==403
    assert c.put(url,headers=owner,json={'amount':150}).status_code==200
    summary=c.get('/api/expenses/summary',headers=owner).json();assert summary['count']==1 and summary['total_amount']==150
    assert c.get('/api/expenses',headers=owner).json()['total']==1
    assert c.delete(url,headers=outsider).status_code==403
    assert c.delete(url,headers=owner).status_code==204

def test_us24_payment_scope_and_history(env):
    c,h,tenant,_,_,cid=env
    dep=application.dependency_overrides[get_db](); db=next(dep)
    try:
        other=User(full_name='Other landlord',email='other-payment@example.com',role='landlord',password_hash='x')
        db.add(other);db.commit()
        outsider={'Authorization':'Bearer '+create_access_token(other.id)}
    finally:
        dep.close()
    bill=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':date.today().strftime('%Y-%m')})
    assert bill.status_code==201
    payment_url=f'/api/invoices/{bill.json()["id"]}/payments'
    assert c.post(payment_url,headers=outsider,json={'amount':100,'method':'cash'}).status_code==403
    assert c.post(payment_url,headers=tenant,json={'amount':100,'method':'cash'}).status_code==403
    paid=c.post(payment_url,headers=h,json={'amount':100,'method':'bank_transfer','note':'demo'})
    assert paid.status_code==201 and paid.json()['remaining_amount']==0
    history=c.get(payment_url,headers=h)
    assert history.status_code==200 and len(history.json())==1 and history.json()[0]['note']=='demo'
    assert c.get(payment_url,headers=outsider).status_code==403

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    assert engine.url.database in (None, '', ':memory:')
    from app.db.invoice_snapshot import invoice_snapshot
    Base.metadata.create_all(engine); reading_revision.create(engine); invoice_snapshot.create(engine)
    Session=sessionmaker(engine,expire_on_commit=False)
    with Session.begin() as db:
        user=User(full_name='Owner',email='owner@example.com',role='landlord',password_hash='x');tenantuser=User(full_name='Tenant',email='tenant@example.com',role='tenant',password_hash='x');db.add_all([user,tenantuser]);db.flush()
        prop=Property(owner_id=user.id,name='Property',address='A',electricity_unit_price=10,water_unit_price=20,service_unit_price=0);db.add(prop);db.flush()
        room=Room(property_id=prop.id,room_number='A',base_rent=100,status='occupied');tenant=TenantProfile(landlord_id=user.id,created_by=user.id,full_name='T',phone='0900000000',id_number='123456789012');db.add_all([room,tenant]);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tenant.id,created_by=user.id,start_date=date.today()-timedelta(days=30),end_date=date.today()+timedelta(days=30),deposit=100,monthly_rent=100,status='active');db.add(contract);db.flush(); uid,tid,rid,pid,cid=user.id,tenantuser.id,room.id,prop.id,contract.id
    def dep():
        with Session() as db: yield db
    application.dependency_overrides[get_db]=dep
    yield TestClient(application), {'Authorization':'Bearer '+create_access_token(uid)}, {'Authorization':'Bearer '+create_access_token(tid)}, rid,pid,cid
    application.dependency_overrides.clear();engine.dispose()


def test_readings_revision_and_aba(env):
    c,h,t,rid,_,_=env; url=f'/api/rooms/{rid}/readings'; period=date.today().strftime('%Y-%m')
    for kind in ('electricity','water'):
        data={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':5}
        r=c.post(url,headers=h,json=data); assert r.status_code==201
        assert c.post(url,headers=h,json=data).status_code==409
        rid2=r.json()['id']; put=f'{url}/{rid2}'
        def edit(value,version): return c.put(put,headers=h,json={'previous_reading':0,'current_reading':value,'expected_version':version})
        assert edit(6,0).status_code==200
        assert edit(5,1).status_code==200
        assert edit(7,0).status_code==409
        assert c.get(put+'/version',headers=h).json()=={'version':2}
        assert c.put(put,headers=t,json={'previous_reading':0,'current_reading':7,'expected_version':2}).status_code==403
    assert c.post(url,headers=h,json={'utility_type':'water','period':'2026-13','previous_reading':0,'current_reading':1}).status_code==422
    assert c.post(url,headers=h,json={'utility_type':'water','period':'2026-01','previous_reading':5,'current_reading':4}).status_code==422
    assert c.post(url,headers=h,json={'utility_type':'water','period':'0000-01','previous_reading':0,'current_reading':1}).status_code==422
    assert c.put(f'{url}/99999',headers=h,json={'previous_reading':0,'current_reading':1,'expected_version':0}).status_code==404


def test_us22_wifi_does_not_omit_electricity(env):
    c,h,_,rid,pid,cid=env; period=date.today().strftime('%Y-%m')
    assert c.put(f'/api/properties/{pid}/service-prices/wifi',headers=h,json={'billing_unit':'room_month','unit_price':20}).status_code==200
    assert c.post('/api/service-assignments',headers=h,json={'service_code':'wifi','room_id':rid}).status_code==201
    reading=c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':'electricity','period':period,'previous_reading':0,'current_reading':5});assert reading.status_code==201
    invoice=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period});assert invoice.status_code==201
    assert invoice.json()['utility_amount']==70 and invoice.json()['total_amount']==170
    assert c.put(f'/api/rooms/{rid}/readings/{reading.json()["id"]}',headers=h,json={'previous_reading':0,'current_reading':6,'expected_version':0}).status_code==409
    assert c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period}).status_code==409
    assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':'water','period':period,'previous_reading':0,'current_reading':5}).status_code==409


def test_us22_meter_prices_are_not_counted_twice(env):
    c,h,_,rid,pid,cid=env;period=date.today().strftime('%Y-%m')
    for code,unit,price in [('electricity','kwh',100),('wifi','room_month',20)]:
        assert c.put(f'/api/properties/{pid}/service-prices/{code}',headers=h,json={'billing_unit':unit,'unit_price':price}).status_code==200
        assert c.post('/api/service-assignments',headers=h,json={'service_code':code,'room_id':rid}).status_code==201
    for kind,current in [('electricity',5),('water',3)]:
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':current}).status_code==201
    invoice=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period})
    assert invoice.status_code==201 and invoice.json()['utility_amount']==580 and invoice.json()['total_amount']==680


def test_lock_error_rolls_back_without_retry():
    from sqlalchemy.exc import OperationalError
    from fastapi import HTTPException
    from app.services.db_util import execute_write
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as db:
        def operation(session):
            session.add(User(full_name='X',email='rollback@example.com',role='tenant',password_hash='x'));session.flush()
            raise OperationalError('statement',{},Exception('simulated deadlock'))
        with pytest.raises(HTTPException) as exc: execute_write(db,operation)
        assert exc.value.status_code==503
        assert db.query(User).count()==0
    engine.dispose()


def test_reading_scope_for_manager_and_other_landlord(env):
    from app.models.boarding import PropertyManager
    c,h,t,rid,pid,cid=env
    dependency=application.dependency_overrides[get_db](); db=next(dependency)
    try:
        manager=User(full_name='Assigned',email='assigned@example.com',role='manager',password_hash='x')
        unassigned=User(full_name='Unassigned',email='unassigned@example.com',role='manager',password_hash='x')
        other=User(full_name='Other',email='other@example.com',role='landlord',password_hash='x')
        db.add_all([manager,unassigned,other]);db.flush();db.add(PropertyManager(property_id=pid,user_id=manager.id));db.commit()
        tokens=[{'Authorization':'Bearer '+create_access_token(u.id)} for u in (manager,unassigned,other)]
    finally: dependency.close()
    url=f'/api/rooms/{rid}/readings'; data={'utility_type':'water','period':'2026-02','previous_reading':0,'current_reading':2}
    assert c.post(url,headers=tokens[0],json=data).status_code==201
    assert c.get(url,headers=tokens[1]).status_code==403
    assert c.get(url,headers=tokens[2]).status_code==403
    assert c.get(url,headers=t).status_code==403
    assert c.get(url).status_code==401
    assert c.get(url,headers={'Authorization':'Bearer invalid'}).status_code==401
    assert c.get(f'/api/contracts/{cid}/liquidation-preview',headers=tokens[1]).status_code==403
