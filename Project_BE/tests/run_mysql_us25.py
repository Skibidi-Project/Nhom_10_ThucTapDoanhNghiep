"""Create a fresh local MySQL test database; never use products_db."""
import os,secrets,sys,uuid
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import create_engine,select,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

url=make_url(os.environ['MINISTAY_MYSQL_SERVER_URL'])
if url.get_backend_name()!='mysql' or url.host not in ('localhost','127.0.0.1') or (url.port or 3306)!=3306:
    raise SystemExit('Refusing non-local server')
name='ministay_us25_test_'+uuid.uuid4().hex[:12]
engine=create_engine(url.set(database=None))
with engine.begin() as c:c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
engine.dispose(); os.environ['DATABASE_URL']=url.set(database=name).render_as_string(hide_password=False);os.environ['JWT_SECRET']=secrets.token_urlsafe(48)
from app.db.database import Base
import app.models,app.models.room_type
from app.models.user import User
from app.models.boarding import Property,Room,TenantProfile,Contract,Invoice,Payment
from app.core.security import create_access_token
from app.main import app
from fastapi.testclient import TestClient
engine=create_engine(os.environ['DATABASE_URL']);Base.metadata.create_all(engine)
with Session(engine) as db,db.begin():
    u=User(full_name='Test',email='owner@test.invalid',role='landlord',password_hash='x');db.add(u);db.flush()
    p=Property(owner_id=u.id,name='T',address='T');db.add(p);db.flush()
    r=Room(property_id=p.id,room_number='T',base_rent=100,status='occupied');t=TenantProfile(landlord_id=u.id,created_by=u.id,full_name='T',phone='0900000000',id_number='123456789012');db.add_all([r,t]);db.flush()
    contract=Contract(room_id=r.id,tenant_id=t.id,created_by=u.id,start_date=date.today()-timedelta(days=1),end_date=date.today()+timedelta(days=30),monthly_rent=100,deposit=0,status='active');db.add(contract);db.flush()
    invoice=Invoice(contract_id=contract.id,period=date.today().strftime('%Y-%m'),rent_amount=100,utility_amount=0,total_amount=100,status='unpaid');db.add(invoice);db.flush();uid,iid=u.id,invoice.id
headers={'Authorization':'Bearer '+create_access_token(uid)};barrier=Barrier(2)
def pay(amount):
    barrier.wait();return TestClient(app).post(f'/api/invoices/{iid}/payments',headers=headers,json={'amount':amount,'method':'cash'})
with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(pay,40);b=pool.submit(pay,60);responses=[a.result(),b.result()]
assert [r.status_code for r in responses]==[201,201],[(r.status_code,r.text) for r in responses]
with Session(engine) as db:
    assert db.get(Invoice,iid).status=='paid' and sum(p.amount for p in db.scalars(select(Payment).where(Payment.invoice_id==iid)))==100
c=TestClient(app);d=c.get('/api/dashboard/summary',headers=headers);assert d.status_code==200 and d.json()['outstanding']==0 and d.json()['revenue_received']==100
assert c.post(f'/api/invoices/{iid}/payments',headers=headers,json={'amount':1,'method':'cash'}).status_code==409
print('PASS MySQL InnoDB: concurrent partial payments, status, debt and dashboard; isolated database:',name)
engine.dispose()
