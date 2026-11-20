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

@pytest.fixture
def env():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    assert engine.url.database in (None, '', ':memory:')
    Base.metadata.create_all(engine); reading_revision.create(engine)
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
