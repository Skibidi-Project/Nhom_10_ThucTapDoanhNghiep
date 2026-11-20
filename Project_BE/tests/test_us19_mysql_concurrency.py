import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

url=os.environ.get('MINISTAY_MYSQL_TEST_URL')
if not url:
    pytest.skip('Dedicated MySQL test URL not provided',allow_module_level=True)
parsed=make_url(url)
if parsed.get_backend_name()!='mysql' or parsed.host not in ('localhost','127.0.0.1') or (parsed.port or 3306)!=3306 or not (parsed.database or '').startswith('ministay_business_test_'):
    raise RuntimeError('Refusing non-isolated database')
os.environ['DATABASE_URL']=url
from app.db.database import Base
from app.db.reading_revision import reading_revision
import app.models, app.models.room_type
from app.models.user import User
from app.models.boarding import Property,Room,TenantProfile,Contract,Invoice,UtilityReading
from app.core.security import create_access_token
from app.main import app as application
from fastapi.testclient import TestClient

def test_http_invoice_update_race():
    engine=create_engine(url,pool_size=10)
    Base.metadata.create_all(engine)
    migration=(Path(__file__).resolve().parents[1]/'migrations/us19_reading_revisions.sql').read_text(encoding='utf-8')
    with engine.begin() as connection:
        connection.exec_driver_sql(migration)
        engines=connection.exec_driver_sql("SELECT engine FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name IN ('rooms','utility_readings','invoices','reading_revisions')").scalars().all()
        assert len(engines)==4 and set(engines)=={'InnoDB'}
    Session=sessionmaker(engine,expire_on_commit=False)
    with Session.begin() as db:
        user=User(full_name='Owner',email='test@example.com',role='landlord',password_hash='x');db.add(user);db.flush()
        prop=Property(owner_id=user.id,name='Test',address='Test',electricity_unit_price=10,water_unit_price=20,service_unit_price=0);db.add(prop);db.flush()
        tenant=TenantProfile(landlord_id=user.id,created_by=user.id,full_name='Tenant',phone='0900000000',id_number='123456789012');db.add(tenant);db.flush()
        uid,pid,tid=user.id,prop.id,tenant.id
    headers={'Authorization':'Bearer '+create_access_token(uid)};client=TestClient(application);period=date.today().strftime('%Y-%m')
    for index in range(6):
        with Session.begin() as db:
            room=Room(property_id=pid,room_number=f'T{index}',base_rent=100,status='occupied');db.add(room);db.flush()
            contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today()-timedelta(days=40),end_date=date.today()+timedelta(days=40),deposit=0,monthly_rent=100,status='active');db.add(contract);db.flush();rid,cid=room.id,contract.id
        start=client.post(f'/api/rooms/{rid}/readings',headers=headers,json={'utility_type':'electricity','period':period,'previous_reading':0,'current_reading':6});assert start.status_code==201,start.text
        reading=start.json();barrier=Barrier(2)
        def edit():
            barrier.wait();return TestClient(application).put(f'/api/rooms/{rid}/readings/{reading["id"]}',headers=headers,json={'previous_reading':0,'current_reading':8,'expected_version':0}).status_code
        def invoice():
            barrier.wait();return TestClient(application).post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(edit);b=pool.submit(invoice);result=(a.result(),b.result())
        assert result in ((200,201),(409,201)),result
        with Session() as db:
            saved=db.get(UtilityReading,reading['id']); bill=db.scalar(select(Invoice).where(Invoice.contract_id==cid))
            assert bill.utility_amount==(saved.current_reading-saved.previous_reading)*10
            assert bill.utility_amount==(80 if result[0]==200 else 60)
    with Session.begin() as db:
        room=Room(property_id=pid,room_number='CONCURRENT',base_rent=100,status='available');db.add(room);db.flush();rid=room.id
    url_read=f'/api/rooms/{rid}/readings'
    result=client.post(url_read,headers=headers,json={'utility_type':'water','period':period,'previous_reading':0,'current_reading':5}); assert result.status_code==201
    reading_id=result.json()['id'];barrier=Barrier(2)
    def update(value):
        barrier.wait(); return TestClient(application).put(f'{url_read}/{reading_id}',headers=headers,json={'previous_reading':0,'current_reading':value,'expected_version':0}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(update,6);b=pool.submit(update,7);assert sorted((a.result(),b.result()))==[200,409]
    assert client.get(f'{url_read}/{reading_id}/version',headers=headers).json()=={'version':1}
    assert client.put(f'{url_read}/{reading_id}',headers=headers,json={'previous_reading':0,'current_reading':5,'expected_version':1}).status_code==200
    assert client.put(f'{url_read}/{reading_id}',headers=headers,json={'previous_reading':0,'current_reading':8,'expected_version':0}).status_code==409
    barrier=Barrier(2)
    def duplicate():
        barrier.wait(); return TestClient(application).post(url_read,headers=headers,json={'utility_type':'electricity','period':period,'previous_reading':0,'current_reading':1}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(duplicate);b=pool.submit(duplicate);assert sorted((a.result(),b.result()))==[201,409]
    for index,first in enumerate(('update','invoice')):
        with Session.begin() as db:
            room=Room(property_id=pid,room_number=f'ORDER{index}',base_rent=100,status='occupied');db.add(room);db.flush()
            contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today()-timedelta(days=40),end_date=date.today()+timedelta(days=40),deposit=0,monthly_rent=100,status='active');db.add(contract);db.flush();rid,cid=room.id,contract.id
        created=client.post(f'/api/rooms/{rid}/readings',headers=headers,json={'utility_type':'electricity','period':period,'previous_reading':0,'current_reading':6});assert created.status_code==201
        url_update=f'/api/rooms/{rid}/readings/{created.json()["id"]}'
        body={'previous_reading':0,'current_reading':8,'expected_version':0}
        if first=='update':
            assert client.put(url_update,headers=headers,json=body).status_code==200
            bill=client.post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period});assert bill.status_code==201 and bill.json()['utility_amount']==80
        else:
            bill=client.post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period});assert bill.status_code==201 and bill.json()['utility_amount']==60
            assert client.put(url_update,headers=headers,json=body).status_code==409
    from fastapi import HTTPException
    from app.services.db_util import execute_write
    with Session() as db:
        first,second=db.scalars(select(Room.id).where(Room.room_number.in_(['ORDER0','ORDER1'])).order_by(Room.id)).all()
    deadlock_barrier=Barrier(2)
    def deadlock_worker(first_id,second_id):
        with Session() as db:
            def operation(session):
                session.scalar(select(Room).where(Room.id==first_id).with_for_update())
                deadlock_barrier.wait(timeout=10)
                session.scalar(select(Room).where(Room.id==second_id).with_for_update())
                session.commit()
                return 200
            try:return execute_write(db,operation)
            except HTTPException as exc:return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(deadlock_worker,first,second);b=pool.submit(deadlock_worker,second,first)
        assert sorted((a.result(),b.result()))==[200,503]
    from sqlalchemy.exc import OperationalError
    with Session() as db:
        def fail_after_flush(session):
            session.add(User(full_name='Rollback',email='rollback@example.com',role='tenant',password_hash='x'))
            session.flush()
            raise OperationalError('simulated failure',{},Exception('forced'))
        with pytest.raises(HTTPException): execute_write(db,fail_after_flush)
    with Session() as db:
        assert db.scalar(select(User.id).where(User.email=='rollback@example.com')) is None
    engine.dispose()
