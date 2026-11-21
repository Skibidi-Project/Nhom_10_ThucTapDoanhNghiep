"""Create a fresh local MySQL test database; never use products_db."""
import os,secrets,sys,uuid
from pathlib import Path
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from sqlalchemy import create_engine,select,text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

url=make_url(os.environ['MINISTAY_MYSQL_SERVER_URL'])
if url.get_backend_name()!='mysql' or url.host not in ('localhost','127.0.0.1') or (url.port or 3306)!=3306:
    raise SystemExit('Refusing non-local server')
name='ministay_us25_test_'+uuid.uuid4().hex[:12]
engine=create_engine(url.set(database=None))
with engine.begin() as c:c.execute(text('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4'))
engine.dispose()
# Exercise the actual migration against a separate pre-existing minimal schema.
migration_name='ministay_us25_test_'+uuid.uuid4().hex[:12]
engine=create_engine(url.set(database=None))
with engine.begin() as c:c.execute(text('CREATE DATABASE `'+migration_name+'` CHARACTER SET utf8mb4'))
engine.dispose(); migration_engine=create_engine(url.set(database=migration_name))
with migration_engine.begin() as c:
    c.execute(text('CREATE TABLE users (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB'))
    c.execute(text('CREATE TABLE invoices (id INT NOT NULL PRIMARY KEY) ENGINE=InnoDB'))
    c.execute(text('CREATE TABLE payments (id INT NOT NULL PRIMARY KEY, invoice_id INT NOT NULL, recorded_by INT NOT NULL) ENGINE=InnoDB'))
    c.execute(text('INSERT INTO invoices (id) VALUES (1)'))
    c.execute(text('INSERT INTO payments (id,invoice_id,recorded_by) VALUES (1,1,1)'))
    sql=(Path(__file__).resolve().parents[1]/'migrations/us25_due_date_mysql.sql').read_text(encoding='utf-8-sig')
    sql='\n'.join(line for line in sql.splitlines() if not line.strip().startswith('--'))
    for statement in sql.split(';'):
        if statement.strip():c.execute(text(statement))
    assert c.execute(text('SELECT due_date FROM invoices WHERE id=1')).one()[0] is None
    c.execute(text("INSERT INTO users (id) VALUES (1)"))
    c.execute(text("INSERT INTO invoice_due_date_history (invoice_id,new_due_date,reason,changed_by,changed_at) VALUES (1,'2026-01-01','agreement',1,NOW())"))
    assert c.execute(text('SELECT COUNT(*) FROM invoice_due_date_history')).scalar_one()==1
    sql=(Path(__file__).resolve().parents[1]/'migrations/us24_payment_idempotency_mysql.sql').read_text(encoding='utf-8-sig')
    sql='\n'.join(line for line in sql.splitlines() if not line.strip().startswith('--'))
    for statement in sql.split(';'):
        if statement.strip():c.execute(text(statement))
    assert c.execute(text('SELECT idempotency_key FROM payments WHERE id=1')).scalar_one() is None
migration_engine.dispose()
os.environ['DATABASE_URL']=url.set(database=name).render_as_string(hide_password=False);os.environ['JWT_SECRET']=secrets.token_urlsafe(48)
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
c=TestClient(app)
assert c.put(f'/api/invoices/{iid}/due-date',headers=headers,json={'due_date':(date.today()-timedelta(days=1)).isoformat(),'reason':'Test agreement'}).json()['effective_status']=='overdue'
def pay(amount):
    barrier.wait();return TestClient(app).post(f'/api/invoices/{iid}/payments',headers={**headers,'Idempotency-Key':'same-test-key'},json={'amount':amount,'method':'cash'})
with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(pay,40);b=pool.submit(pay,40);responses=[a.result(),b.result()]
assert [r.status_code for r in responses]==[201,201],[(r.status_code,r.text) for r in responses]
assert responses[0].json()['id']==responses[1].json()['id']
assert c.post(f'/api/invoices/{iid}/payments',headers={**headers,'Idempotency-Key':'same-test-key'},json={'amount':41,'method':'cash'}).status_code==409
assert c.post(f'/api/invoices/{iid}/payments',headers={**headers,'Idempotency-Key':'another-test-key'},json={'amount':60,'method':'cash'}).status_code==201
with Session(engine) as db:
    assert db.get(Invoice,iid).status=='paid' and sum(p.amount for p in db.scalars(select(Payment).where(Payment.invoice_id==iid)))==100
c=TestClient(app);d=c.get('/api/dashboard/summary',headers=headers);assert d.status_code==200 and d.json()['outstanding']==0 and d.json()['revenue_received']==100
assert c.post(f'/api/invoices/{iid}/payments',headers=headers,json={'amount':1,'method':'cash'}).status_code==409
try:
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO payments(invoice_id,amount,method,recorded_by,paid_at) VALUES (999999,1,'cash',:uid,NOW())"),{'uid':uid})
    raise AssertionError('Foreign key not enforced')
except IntegrityError:
    pass
with engine.connect() as conn:
    tx=conn.begin();conn.execute(text('UPDATE invoices SET total_amount=999 WHERE id=:id'),{'id':iid});tx.rollback()
with Session(engine) as db:
    assert db.get(Invoice,iid).total_amount==100
    duplicate=Invoice(contract_id=db.get(Invoice,iid).contract_id,period=db.get(Invoice,iid).period,rent_amount=1,utility_amount=0,total_amount=1,status='unpaid');db.add(duplicate)
    try:db.commit();raise AssertionError('Unique constraint not enforced')
    except IntegrityError:db.rollback()
with engine.begin() as conn:
    conn.execute(text('CREATE TABLE deadlock_probe (id INT PRIMARY KEY, n INT NOT NULL) ENGINE=InnoDB'))
    conn.execute(text('INSERT INTO deadlock_probe VALUES (1,0),(2,0)'))
sync=Barrier(2)
def deadlock(a,b):
    try:
        with engine.begin() as conn:
            conn.execute(text('UPDATE deadlock_probe SET n=n+1 WHERE id=:id'),{'id':a})
            sync.wait(timeout=10)
            conn.execute(text('UPDATE deadlock_probe SET n=n+1 WHERE id=:id'),{'id':b})
        return 'committed'
    except OperationalError as exc:
        if exc.orig.args[0] != 1213:raise
        return 'deadlock'
with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(deadlock,1,2);b=pool.submit(deadlock,2,1);outcomes=sorted([a.result(),b.result()])
assert outcomes==['committed','deadlock'],outcomes
with engine.connect() as conn:
    assert conn.execute(text('SELECT SUM(n) FROM deadlock_probe')).scalar_one()==2
print('PASS MySQL InnoDB: migration, FK, unique, rollback, deadlock, concurrent payments and dashboard; isolated databases:',name,migration_name)
engine.dispose()
