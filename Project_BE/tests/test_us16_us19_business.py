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
    from app.db.settlement_trial import metadata as settlement_metadata
    from app.db.invoice_snapshot import invoice_snapshot
    Base.metadata.create_all(engine); reading_revision.create(engine); settlement_metadata.create_all(engine); invoice_snapshot.create(engine)
    Session=sessionmaker(engine,expire_on_commit=False)
    with Session.begin() as db:
        user=User(full_name='Owner',email='owner@example.com',role='landlord',password_hash='x');tenantuser=User(full_name='Tenant',email='tenant@example.com',role='tenant',password_hash='x');db.add_all([user,tenantuser]);db.flush()
        prop=Property(owner_id=user.id,name='Property',address='A',electricity_unit_price=10,water_unit_price=20,service_unit_price=0);db.add(prop);db.flush()
        room=Room(property_id=prop.id,room_number='A',base_rent=100,status='occupied');tenant=TenantProfile(landlord_id=user.id,created_by=user.id,full_name='T',phone='0900000000',id_number='123456789012');db.add_all([room,tenant]);db.flush()
        contract=Contract(room_id=room.id,tenant_id=tenant.id,created_by=user.id,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=30),deposit=100,monthly_rent=100,status='active');db.add(contract);db.flush(); uid,tid,rid,pid,cid=user.id,tenantuser.id,room.id,prop.id,contract.id
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

def test_liquidation_is_read_only_until_rules_approved(env):
    c,h,t,_,_,cid=env
    r=c.get(f'/api/contracts/{cid}/liquidation-preview',headers=h); assert r.status_code==200 and r.json()['deposit']==100 and r.json()['outstanding']==0
    assert c.get(f'/api/contracts/{cid}/liquidation-preview',headers=t).status_code==403
    assert c.post(f'/api/contracts/{cid}/liquidate',headers=h).status_code==409

@pytest.mark.parametrize('damage,refund,shortfall', [(0,100,0),(30,70,0),(100,0,0),(150,0,50)])
def test_trial_settlement_keeps_debt_separate(env, monkeypatch, damage, refund, shortfall):
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,t,rid,_,cid=env
    root=f'/api/contracts/{cid}'
    assert c.patch(root+'/deposit',headers=h,json={'status':'held'}).status_code==200
    period=date.today().strftime('%Y-%m')
    for kind in ('electricity','water'):
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':0}).status_code==201
    invoice=c.post(root+'/invoices',headers=h,json={'period':date.today().strftime('%Y-%m')})
    assert invoice.status_code==201
    handover={'actual_end_date':date.today().isoformat(),'reason':'Bàn giao','confirmed':True}
    assert c.post(root+'/liquidate',headers=t,json=handover).status_code==403
    assert c.post(root+'/liquidate',headers=h,json=handover).status_code==200
    assert c.post(root+'/liquidate',headers=h,json=handover).status_code==409
    if damage:
        assert c.post(root+'/liquidation-damages',headers=h,json={'description':'Hư hỏng','amount':damage,'confirmed':True}).status_code==200
    preview=c.get(root+'/liquidation-preview',headers=h).json()
    assert preview['estimated_refund']==refund and preview['outstanding']==100
    assert c.post(root+'/liquidation-refund',headers=h,json={'confirmed':True,'method':'cash'}).status_code==409
    assert c.get(root+'/liquidation-preview',headers=h).json()['settlement']['refund_amount'] is None
    payment=c.post(f'/api/invoices/{invoice.json()["id"]}/payments',headers=h,json={'amount':100,'method':'cash'})
    assert payment.status_code==201, payment.text
    assert c.post(root+'/liquidation-refund',headers=h,json={'confirmed':True,'method':'cash'}).status_code==409
    # Only exercise the arithmetic and idempotency under explicitly simulated evidence.
    from app.services import settlement_trial
    monkeypatch.setattr(settlement_trial,'final_invoice_evidence_is_complete',lambda *args: True)
    assert c.post(root+'/liquidation-refund',headers=h,json={'confirmed':True,'method':'cash'}).status_code==409
    monkeypatch.setattr(settlement_trial,'final_meter_handover_is_verified',lambda *args: True)
    result=c.post(root+'/liquidation-refund',headers=h,json={'confirmed':True,'method':'cash'})
    if shortfall:
        assert result.status_code==409
        saved=c.get(root+'/liquidation-preview',headers=h).json()
        assert saved['receivable']['amount']==shortfall and saved['receivable']['status']=='unpaid'
        assert saved['settlement']['refund_amount'] is None
        return
    assert result.status_code==200, result.text
    assert result.json()['refund_amount']==refund and result.json()['damage_shortfall']==shortfall
    saved=c.get(root+'/liquidation-preview',headers=h).json()
    assert saved['receivable'] is None
    assert c.post(root+'/liquidation-refund',headers=h,json={'confirmed':True,'method':'cash'}).status_code==409
    assert c.get(root+'/liquidation-preview',headers=h).json()['outstanding']==0

def test_trial_forbidden_without_flag(env,monkeypatch):
    monkeypatch.delenv('MINISTAY_US16_TRIAL',raising=False)
    c,h,_,_,_,cid=env
    r=c.post(f'/api/contracts/{cid}/liquidation-damages',headers=h,json={'description':'x','amount':1})
    assert r.status_code==409
    r=c.patch(f'/api/contracts/{cid}/deposit',headers=h,json={'status':'returned','returned_amount':1})
    assert r.status_code==409

def test_damage_confirmation_scope_and_audit(env,monkeypatch):
    from app.models.boarding import PropertyManager
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,tenant,_,pid,cid=env
    dep=application.dependency_overrides[get_db]();db=next(dep)
    try:
        assigned=User(full_name='Assigned',email='manager-trial@example.com',role='manager',password_hash='x')
        outsider=User(full_name='Other',email='other-trial@example.com',role='manager',password_hash='x')
        db.add_all([assigned,outsider]);db.flush();db.add(PropertyManager(property_id=pid,user_id=assigned.id));db.commit()
        manager={'Authorization':'Bearer '+create_access_token(assigned.id)}
        other={'Authorization':'Bearer '+create_access_token(outsider.id)}
    finally: dep.close()
    root=f'/api/contracts/{cid}/liquidation-damages'
    result=c.post(root,headers=h,json={'description':'Hư hỏng','amount':30,'confirmed':False})
    assert result.status_code==200
    url=f'{root}/{result.json()["id"]}/confirm'
    assert c.post(url,headers=tenant).status_code==403
    assert c.post(url,headers=other).status_code==403
    assert c.post(url,headers=manager).status_code==200
    assert c.post(url,headers=manager).status_code==409
    item=c.get(f'/api/contracts/{cid}/liquidation-preview',headers=h).json()['damages'][0]
    assert item['confirmed_by'] and item['confirmed_at']

def test_manual_final_approval_scope_and_aba(env,monkeypatch):
    from app.models.boarding import PropertyManager
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,owner,tenant,rid,pid,cid=env; period=date.today().strftime('%Y-%m')
    dep=application.dependency_overrides[get_db]();db=next(dep)
    try:
        manager=User(full_name='Manager',email='final-manager@example.com',role='manager',password_hash='x')
        other=User(full_name='Other',email='final-other@example.com',role='landlord',password_hash='x')
        db.add_all([manager,other]);db.flush();db.add(PropertyManager(property_id=pid,user_id=manager.id));db.commit()
        mh={'Authorization':'Bearer '+create_access_token(manager.id)};oh={'Authorization':'Bearer '+create_access_token(other.id)}
    finally:dep.close()
    readings=f'/api/rooms/{rid}/readings'
    reading=c.post(readings,headers=owner,json={'utility_type':'electricity','period':period,'previous_reading':0,'current_reading':5});assert reading.status_code==201
    root=f'/api/contracts/{cid}/final-approvals'
    data={'period_start':date.today().replace(day=1).isoformat(),'period_end':date.today().isoformat(),'charge_type':'rent','reason':'Thiếu điều khoản','proposed_method':'Thỏa thuận','proposed_amount':40,'reference':'Phụ lục thử'}
    assert c.post(root,headers=tenant,json=data).status_code==403
    assert c.post(root,headers=oh,json=data).status_code==403
    first=c.post(root,headers=mh,json=data);assert first.status_code==201,first.text
    assert c.post(root,headers=owner,json=data).status_code==409
    decision=f'{root}/{first.json()["id"]}/decision'
    assert c.post(decision,headers=mh,json={'approved':True,'reason':'Duyệt'}).status_code==403
    reading_url=f'{readings}/{reading.json()["id"]}'
    assert c.put(reading_url,headers=owner,json={'previous_reading':0,'current_reading':6,'expected_version':0}).status_code==200
    assert c.put(reading_url,headers=owner,json={'previous_reading':0,'current_reading':5,'expected_version':1}).status_code==200
    assert c.get(root,headers=owner).json()[0]['status']=='stale'
    assert c.post(decision,headers=owner,json={'approved':True,'reason':'Duyệt'}).status_code==409
    new=c.post(root,headers=owner,json=data);assert new.status_code==201
    decision=f'{root}/{new.json()["id"]}/decision'
    assert c.post(decision,headers=owner,json={'approved':True,'reason':'Theo phụ lục'}).status_code==200
    assert c.post(decision,headers=owner,json={'approved':True,'reason':'Lặp'}).status_code==409
    result=c.get(root,headers=owner).json()[-1]
    assert result['status']=='approved' and result['reviewed_by'] and result['reviewed_at'] and result['decision_reason']
    invoice=c.post(f'/api/contracts/{cid}/invoices',headers=owner,json={'period':period})
    assert invoice.status_code==409 and 'cuối kỳ' in invoice.json()['detail']

def test_trial_price_aba_invalidates_manual_approval(env,monkeypatch):
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,owner,_,_,pid,cid=env
    price=f'/api/properties/{pid}/service-prices/wifi'
    assert c.put(price,headers=owner,json={'billing_unit':'room_month','unit_price':20}).status_code==200
    root=f'/api/contracts/{cid}/final-approvals'
    body={'period_start':date.today().replace(day=1).isoformat(),'period_end':date.today().isoformat(),'charge_type':'rent','reason':'Thiếu điều khoản','proposed_method':'Thỏa thuận','proposed_amount':40,'reference':'Biên bản'}
    req=c.post(root,headers=owner,json=body);assert req.status_code==201,req.text
    assert c.put(price,headers=owner,json={'billing_unit':'room_month','unit_price':30}).status_code==200
    assert c.put(price,headers=owner,json={'billing_unit':'room_month','unit_price':20}).status_code==200
    assert c.get(root,headers=owner).json()[0]['status']=='stale'
    assert c.post(f'{root}/{req.json()["id"]}/decision',headers=owner,json={'approved':True,'reason':'Duyệt'}).status_code==409

def test_final_period_requires_all_invoices_and_both_readings(env,monkeypatch):
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,_,rid,_,cid=env;root=f'/api/contracts/{cid}'
    data={'actual_end_date':date.today().isoformat(),'reason':'Trả phòng','confirmed':True}
    preview=c.get(root+'/liquidation-preview',headers=h).json()
    assert len(preview['final_period_gaps'])==3
    blocked=c.post(root+'/liquidate',headers=h,json=data)
    assert blocked.status_code==409 and 'Thiếu hóa đơn' in blocked.json()['detail']
    period=date.today().strftime('%Y-%m')
    for kind in ('electricity','water'):
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':0}).status_code==201
    invoice=c.post(root+'/invoices',headers=h,json={'period':period});assert invoice.status_code==201
    review=f'{root}/liquidation-invoices/{invoice.json()["id"]}/review'
    assert c.post(review,headers=h).status_code==200
    assert c.post(review,headers=h).status_code==409
    assert c.post(root+'/liquidate',headers=h,json=data).status_code==200

def test_final_evidence_requires_snapshot_review_and_month_end(env,monkeypatch):
    import calendar
    from app.services.settlement_trial import final_invoice_evidence_is_complete
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,_,rid,_,cid=env;period=date.today().strftime('%Y-%m')
    for kind in ('electricity','water'):
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':1}).status_code==201
    invoice=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period});assert invoice.status_code==201
    last=date.today().replace(day=calendar.monthrange(date.today().year,date.today().month)[1])
    def check(end):
        dep=application.dependency_overrides[get_db]();db=next(dep)
        try: return final_invoice_evidence_is_complete(db,db.get(Contract,cid),{'handover_date':end})
        finally: dep.close()
    assert not check(last)
    assert c.post(f'/api/contracts/{cid}/liquidation-invoices/{invoice.json()["id"]}/review',headers=h).status_code==200
    assert not check(last)  # an ordinary monthly invoice is not a final invoice
    assert not check(last.replace(day=1))

def test_final_manual_settlement_with_real_evidence(env,monkeypatch):
    from datetime import datetime
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,_,rid,_,cid=env;period=date.today().strftime('%Y-%m');root=f'/api/contracts/{cid}'
    assert c.patch(root+'/deposit',headers=h,json={'status':'held'}).status_code==200
    ids={}
    for kind,value in [('electricity',5),('water',3)]:
        r=c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':value});assert r.status_code==201
        ids[kind]=r.json()['id']
    meter=c.post(root+'/final-meter-handover',headers=h,json={'handover_at':datetime.now().replace(microsecond=0).isoformat(),'electricity_reading_id':ids['electricity'],'water_reading_id':ids['water'],'electricity_expected_version':0,'water_expected_version':0})
    assert meter.status_code==201,meter.text
    for kind,amount in [('rent',100),('electricity',50),('water',60)]:
        body={'period_start':date.today().replace(day=1).isoformat(),'period_end':date.today().isoformat(),'charge_type':kind,'reason':'Thiếu điều khoản','proposed_method':'Thỏa thuận thử nghiệm','proposed_amount':amount,'reference':'Biên bản thử'}
        req=c.post(root+'/final-approvals',headers=h,json=body);assert req.status_code==201,req.text
        approve=c.post(f'{root}/final-approvals/{req.json()["id"]}/decision',headers=h,json={'approved':True,'reason':'Đã kiểm tra'});assert approve.status_code==200,approve.text
    issue=c.post(root+'/final-invoice',headers=h);assert issue.status_code==201,issue.text
    invoice_id=issue.json()['invoice_id'];assert issue.json()['total_amount']==210
    assert c.post(root+'/final-invoice',headers=h).status_code==409
    evidence=c.get(f'/api/invoices/{invoice_id}/snapshot',headers=h);assert evidence.json()['status']=='complete'
    assert evidence.json()['document']['billing_kind']=='final_manual'
    assert c.post(f'{root}/liquidation-invoices/{invoice_id}/review',headers=h).status_code==200
    handover=c.post(root+'/liquidate',headers=h,json={'actual_end_date':date.today().isoformat(),'reason':'Bàn giao','confirmed':True});assert handover.status_code==200,handover.text
    refund={'confirmed':True,'method':'cash'}
    assert c.post(root+'/liquidation-refund',headers=h,json=refund).status_code==409
    assert c.post(f'/api/invoices/{invoice_id}/payments',headers=h,json={'amount':210,'method':'cash'}).status_code==201
    result=c.post(root+'/liquidation-refund',headers=h,json=refund);assert result.status_code==200,result.text
    assert result.json()['refund_amount']==100
    assert c.post(root+'/liquidation-refund',headers=h,json=refund).status_code==409

def test_final_meter_aba_blocks_invoice(env,monkeypatch):
    from datetime import datetime
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,_,rid,_,cid=env;period=date.today().strftime('%Y-%m');root=f'/api/contracts/{cid}'
    ids={}
    for kind,value in [('electricity',5),('water',3)]:
        result=c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':value});assert result.status_code==201;ids[kind]=result.json()['id']
    result=c.post(root+'/final-meter-handover',headers=h,json={'handover_at':datetime.now().replace(microsecond=0).isoformat(),'electricity_reading_id':ids['electricity'],'water_reading_id':ids['water'],'electricity_expected_version':0,'water_expected_version':0});assert result.status_code==201
    target=f'/api/rooms/{rid}/readings/{ids["electricity"]}'
    assert c.put(target,headers=h,json={'previous_reading':0,'current_reading':6,'expected_version':0}).status_code==200
    assert c.put(target,headers=h,json={'previous_reading':0,'current_reading':5,'expected_version':1}).status_code==200
    result=c.post(root+'/final-invoice',headers=h)
    assert result.status_code==409 and 'chỉ số bàn giao' in result.json()['detail'].lower()

def test_meter_confirmation_rejects_stale_version(env,monkeypatch):
    from datetime import datetime
    monkeypatch.setenv('MINISTAY_US16_TRIAL','1')
    c,h,_,rid,_,cid=env;period=date.today().strftime('%Y-%m');ids={}
    for kind in ('electricity','water'):
        result=c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':5});assert result.status_code==201;ids[kind]=result.json()['id']
    assert c.put(f'/api/rooms/{rid}/readings/{ids["electricity"]}',headers=h,json={'previous_reading':0,'current_reading':6,'expected_version':0}).status_code==200
    body={'handover_at':datetime.now().replace(microsecond=0).isoformat(),'electricity_reading_id':ids['electricity'],'water_reading_id':ids['water'],'electricity_expected_version':0,'water_expected_version':0}
    assert c.post(f'/api/contracts/{cid}/final-meter-handover',headers=h,json=body).status_code==409

def test_us22_meter_prices_are_not_counted_twice(env):
    c,h,_,rid,pid,cid=env;period=date.today().strftime('%Y-%m')
    for code,unit,price in [('electricity','kwh',100),('wifi','room_month',20)]:
        assert c.put(f'/api/properties/{pid}/service-prices/{code}',headers=h,json={'billing_unit':unit,'unit_price':price}).status_code==200
        assert c.post('/api/service-assignments',headers=h,json={'service_code':code,'room_id':rid}).status_code==201
    for kind,current in [('electricity',5),('water',3)]:
        assert c.post(f'/api/rooms/{rid}/readings',headers=h,json={'utility_type':kind,'period':period,'previous_reading':0,'current_reading':current}).status_code==201
    invoice=c.post(f'/api/contracts/{cid}/invoices',headers=h,json={'period':period})
    assert invoice.status_code==201 and invoice.json()['utility_amount']==580 and invoice.json()['total_amount']==680

def test_settlement_preview_preserves_invoice_and_payment(env):
    from app.models.boarding import Invoice, Payment
    c,h,_,_,_,cid=env
    dependency=application.dependency_overrides[get_db]()
    db=next(dependency)
    try:
        invoice=Invoice(contract_id=cid,period='2026-01',rent_amount=100,utility_amount=0,total_amount=100,status='partially_paid');db.add(invoice);db.flush()
        db.add(Payment(invoice_id=invoice.id,amount=30,method='cash',recorded_by=1));db.commit()
    finally: dependency.close()
    result=c.get(f'/api/contracts/{cid}/liquidation-preview',headers=h)
    assert result.status_code==200 and result.json()['outstanding']==70
    assert c.post(f'/api/contracts/{cid}/liquidate',headers=h).status_code==409
    assert c.get(f'/api/contracts/{cid}/liquidation-preview',headers=h).json()['outstanding']==70

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
