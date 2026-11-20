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

def test_http_invoice_update_race(monkeypatch):
    engine=create_engine(url,pool_size=10)
    Base.metadata.create_all(engine)
    migration=(Path(__file__).resolve().parents[1]/'migrations/us19_reading_revisions.sql').read_text(encoding='utf-8')
    with engine.begin() as connection:
        connection.exec_driver_sql(migration)
        connection.exec_driver_sql(migration)
        snapshot_ddl=(Path(__file__).resolve().parents[1]/'migrations/us22_invoice_snapshots.sql').read_text(encoding='utf-8')
        for statement in snapshot_ddl.split(';'):
            statement='\n'.join(line for line in statement.splitlines() if not line.strip().startswith('--')).strip()
            if statement: connection.exec_driver_sql(statement)
        revision_ddl=connection.exec_driver_sql('SHOW CREATE TABLE reading_revisions').one()[1]
        assert 'PRIMARY KEY (`reading_id`)' in revision_ddl and 'FOREIGN KEY (`reading_id`)' in revision_ddl
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
    # US-24 payment and US-19 billing must share a consistent lock order.
    from app.models.boarding import Payment
    with Session.begin() as db:
        room=Room(property_id=pid,room_number='PAY-RACE',base_rent=100,status='occupied');db.add(room);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today()-timedelta(days=30),end_date=date.today()+timedelta(days=30),deposit=0,monthly_rent=100,status='active');db.add(contract);db.flush();cid=contract.id
    bill=client.post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period});assert bill.status_code==201,bill.text
    invoice_id=bill.json()['id']; barrier=Barrier(2)
    def pay():
        barrier.wait()
        return TestClient(application).post(f'/api/invoices/{invoice_id}/payments',headers=headers,json={'amount':100,'method':'cash','note':'concurrent'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(pay);b=pool.submit(pay);assert sorted((a.result(),b.result()))==[201,409]
    with Session() as db:
        records=db.scalars(select(Payment).where(Payment.invoice_id==invoice_id)).all()
        assert len(records)==1 and records[0].amount==100 and records[0].note=='concurrent'
        assert db.get(Invoice,invoice_id).status=='paid'
    history=client.get(f'/api/invoices/{invoice_id}/payments',headers=headers)
    assert history.status_code==200 and len(history.json())==1
    from sqlalchemy.exc import SQLAlchemyError
    for statement in ('UPDATE invoice_snapshots SET payload=payload WHERE invoice_id=%s','DELETE FROM invoice_snapshots WHERE invoice_id=%s'):
        with pytest.raises(SQLAlchemyError):
            with engine.begin() as connection: connection.exec_driver_sql(statement,(invoice_id,))
    with Session.begin() as db:
        room=Room(property_id=pid,room_number='PAY-PARTIAL',base_rent=100,status='occupied');db.add(room);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today()-timedelta(days=30),end_date=date.today()+timedelta(days=30),deposit=0,monthly_rent=100,status='active');db.add(contract);db.flush();cid=contract.id
    bill=client.post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period});assert bill.status_code==201
    invoice_id=bill.json()['id'];barrier=Barrier(2)
    def pay_part(amount):
        barrier.wait()
        return TestClient(application).post(f'/api/invoices/{invoice_id}/payments',headers=headers,json={'amount':amount,'method':'cash'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(pay_part,40);b=pool.submit(pay_part,60);results=[a.result(),b.result()]
    assert all(result.status_code==201 for result in results)
    assert max(result.json()['total_paid'] for result in results)==100
    with Session() as db:
        assert sum(x.amount for x in db.scalars(select(Payment).where(Payment.invoice_id==invoice_id)))==100
        assert db.get(Invoice,invoice_id).status=='paid'
    # Proposed US-16 policies remain restricted to a unique isolated database.
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    ddl=(Path(__file__).resolve().parents[1]/'migrations/us16_settlement_trial.sql').read_text(encoding='utf-8')
    with engine.begin() as connection:
        for statement in ddl.split(';'):
            statement='\n'.join(line for line in statement.splitlines() if not line.strip().startswith('--')).strip()
            if statement: connection.exec_driver_sql(statement)
    with Session.begin() as db:
        room=Room(property_id=pid,room_number='APPROVAL-RACE',base_rent=100,status='occupied');db.add(room);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=30),deposit=100,monthly_rent=100,status='active');db.add(contract);db.flush();approval_contract=contract.id
    approval_url=f'/api/contracts/{approval_contract}/final-approvals'
    request={'period_start':date.today().replace(day=1).isoformat(),'period_end':date.today().isoformat(),'charge_type':'rent','reason':'Thiếu điều khoản','proposed_method':'Thỏa thuận thử','proposed_amount':40}
    barrier=Barrier(2)
    def request_approval():
        barrier.wait();return TestClient(application).post(approval_url,headers=headers,json=request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(request_approval);b=pool.submit(request_approval);answers=[a.result(),b.result()]
    assert sorted(x.status_code for x in answers)==[201,409]
    approval_id=next(x.json()['id'] for x in answers if x.status_code==201);barrier=Barrier(2)
    def decide_approval():
        barrier.wait();return TestClient(application).post(f'{approval_url}/{approval_id}/decision',headers=headers,json={'approved':True,'reason':'Đồng ý'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(decide_approval);b=pool.submit(decide_approval);assert sorted((a.result(),b.result()))==[200,409]
    with Session.begin() as db:
        room=Room(property_id=pid,room_number='SETTLEMENT-RACE',base_rent=100,status='occupied');db.add(room);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tid,created_by=uid,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=30),deposit=100,deposit_status='held',monthly_rent=100,status='active');db.add(contract);db.flush();cid,rid=contract.id,room.id
    for kind in ('electricity','water'):
        assert client.post(f'/api/rooms/{rid}/readings',headers=headers,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':0}).status_code==201
    bill=client.post(f'/api/contracts/{cid}/invoices',headers=headers,json={'period':period});assert bill.status_code==201
    invoice_id=bill.json()['id'];barrier=Barrier(2)
    body={'actual_end_date':date.today().isoformat(),'reason':'Test','confirmed':True}
    def handover():
        barrier.wait()
        return TestClient(application).post(f'/api/contracts/{cid}/liquidate',headers=headers,json=body).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(handover);b=pool.submit(handover);assert sorted((a.result(),b.result()))==[200,409]
    assert client.post(f'/api/contracts/{cid}/liquidation-refund',headers=headers,json={'confirmed':True,'method':'cash'}).status_code==409
    assert client.post(f'/api/invoices/{invoice_id}/payments',headers=headers,json={'amount':100,'method':'cash'}).status_code==201
    assert client.post(f'/api/contracts/{cid}/liquidation-refund',headers=headers,json={'confirmed':True,'method':'cash'}).status_code==409
    # Concurrency test simulates verified evidence; application default remains blocked.
    from app.services import settlement_trial
    monkeypatch.setattr(settlement_trial,'final_invoice_evidence_is_complete',lambda *args: True)
    monkeypatch.setattr(settlement_trial,'final_meter_handover_is_verified',lambda *args: True)
    barrier=Barrier(2)
    def refund():
        barrier.wait()
        return TestClient(application).post(f'/api/contracts/{cid}/liquidation-refund',headers=headers,json={'confirmed':True,'method':'cash'}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(refund);b=pool.submit(refund);assert sorted((a.result(),b.result()))==[200,409]
    preview=client.get(f'/api/contracts/{cid}/liquidation-preview',headers=headers).json()
    assert preview['outstanding']==0 and preview['settlement']['refund_amount']==100
    engine.dispose()

def test_real_trial_manual_invoice_payment_refund(monkeypatch):
    from datetime import datetime
    from app.db.settlement_trial import final_approvals
    from app.db.invoice_snapshot import invoice_snapshot
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    engine=create_engine(url,pool_size=8);Session=sessionmaker(engine,expire_on_commit=False)
    with Session.begin() as db:
        user=User(full_name='Real trial',email='real-trial@example.com',role='landlord',password_hash='x');db.add(user);db.flush()
        prop=Property(owner_id=user.id,name='Real trial',address='A',electricity_unit_price=10,water_unit_price=20,service_unit_price=0);db.add(prop);db.flush()
        room=Room(property_id=prop.id,room_number='REAL',base_rent=100,status='occupied');tenant=TenantProfile(landlord_id=user.id,created_by=user.id,full_name='T',phone='0900000001',id_number='123456789013');db.add_all([room,tenant]);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tenant.id,created_by=user.id,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=30),deposit=100,deposit_status='held',monthly_rent=100,status='active');db.add(contract);db.flush();uid,rid,cid,pid=user.id,room.id,contract.id,prop.id
    headers={'Authorization':'Bearer '+create_access_token(uid)};client=TestClient(application);period=date.today().strftime('%Y-%m');root=f'/api/contracts/{cid}'
    assert client.put(f'/api/properties/{pid}/service-prices/wifi',headers=headers,json={'billing_unit':'room_month','unit_price':20}).status_code==200
    assert client.post('/api/service-assignments',headers=headers,json={'service_code':'wifi','room_id':rid}).status_code==201
    ids={}
    for kind,value in [('electricity',5),('water',3)]:
        result=client.post(f'/api/rooms/{rid}/readings',headers=headers,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':value});assert result.status_code==201,result.text;ids[kind]=result.json()['id']
    result=client.post(root+'/final-meter-handover',headers=headers,json={'handover_at':datetime.now().replace(microsecond=0).isoformat(),'electricity_reading_id':ids['electricity'],'water_reading_id':ids['water'],'electricity_expected_version':0,'water_expected_version':0});assert result.status_code==201,result.text
    for kind,amount in [('rent',100),('electricity',50),('water',60),('service:wifi',20)]:
        body={'period_start':date.today().replace(day=1).isoformat(),'period_end':date.today().isoformat(),'charge_type':kind,'reason':'Điều khoản chưa rõ','proposed_method':'Thỏa thuận thử','proposed_amount':amount,'reference':'Biên bản'}
        result=client.post(root+'/final-approvals',headers=headers,json=body);assert result.status_code==201,result.text
        result=client.post(f'{root}/final-approvals/{result.json()["id"]}/decision',headers=headers,json={'approved':True,'reason':'Đã kiểm tra'});assert result.status_code==200,result.text
    barrier=Barrier(2)
    def issue():
        barrier.wait();return TestClient(application).post(root+'/final-invoice',headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(issue);b=pool.submit(issue);answers=[a.result(),b.result()]
    assert sorted(x.status_code for x in answers)==[201,409],[(x.status_code,x.text) for x in answers]
    invoice_id=next(x.json()['invoice_id'] for x in answers if x.status_code==201)
    assert client.get(f'/api/invoices/{invoice_id}/snapshot',headers=headers).json()['status']=='complete'
    assert client.post(f'{root}/liquidation-invoices/{invoice_id}/review',headers=headers).status_code==200
    result=client.post(root+'/liquidate',headers=headers,json={'actual_end_date':date.today().isoformat(),'reason':'Bàn giao','confirmed':True});assert result.status_code==200,result.text
    assert client.post(root+'/liquidation-refund',headers=headers,json={'confirmed':True,'method':'cash'}).status_code==409
    assert client.post(f'/api/invoices/{invoice_id}/payments',headers=headers,json={'amount':230,'method':'cash'}).status_code==201
    barrier=Barrier(2)
    def refund():
        barrier.wait();return TestClient(application).post(root+'/liquidation-refund',headers=headers,json={'confirmed':True,'method':'cash'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(refund);b=pool.submit(refund);answers=[a.result(),b.result()]
    assert sorted(x.status_code for x in answers)==[200,409],[(x.status_code,x.text) for x in answers]
    with Session() as db:
        assert db.get(Invoice,invoice_id).total_amount==230
        assert db.execute(select(invoice_snapshot).where(invoice_snapshot.c.invoice_id==invoice_id)).first()
        assert set(db.scalars(select(final_approvals.c.status).where(final_approvals.c.contract_id==cid)))=={'invoiced'}
        assert db.get(Contract,cid).status=='expired' and db.get(Room,rid).status=='available'
    engine.dispose()
