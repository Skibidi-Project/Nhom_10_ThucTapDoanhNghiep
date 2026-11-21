import getpass,os,tempfile
from datetime import date,datetime,timedelta
from pathlib import Path
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError,InvalidHashError
from sqlalchemy import inspect,select,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

target=Path(tempfile.gettempdir()).resolve()/'ministay_us25_us27_demo.sqlite3'
url=make_url(os.environ.get('DATABASE_URL','sqlite://'))
if url.get_backend_name()!='sqlite' or not url.database or Path(url.database).resolve()!=target or target.is_symlink(): raise SystemExit('Chỉ cho phép database SQLite demo riêng trong TEMP.')
from app.db.database import Base,engine
import app.models,app.models.room_type
from app.models.user import User
from app.models.boarding import Property,Room,TenantProfile,Contract,Invoice,Payment,InvoiceMonth,InvoiceDueDateHistory,UtilityReading
email='landlord.us25.demo@example.com';pwd=getpass.getpass('Mật khẩu tài khoản demo: ')
if len(pwd)<8:raise SystemExit('Mật khẩu tối thiểu 8 ký tự.')
inspector=inspect(engine)
if inspector.has_table('invoices') and 'due_date' not in {c['name'] for c in inspector.get_columns('invoices')}:
    with engine.begin() as conn: conn.execute(text('ALTER TABLE invoices ADD COLUMN due_date DATE NULL'))
if inspector.has_table('payments'):
    columns={c['name'] for c in inspector.get_columns('payments')}
    with engine.begin() as conn:
        if 'idempotency_key' not in columns: conn.execute(text('ALTER TABLE payments ADD COLUMN idempotency_key VARCHAR(128) NULL'))
        if 'request_fingerprint' not in columns: conn.execute(text('ALTER TABLE payments ADD COLUMN request_fingerprint VARCHAR(64) NULL'))
        conn.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_idempotency ON payments(invoice_id, recorded_by, idempotency_key)'))
Base.metadata.create_all(engine);inspector=inspect(engine)
for table in Base.metadata.sorted_tables:
    if {c.name for c in table.columns}-{c['name'] for c in inspector.get_columns(table.name)}:raise SystemExit('Schema demo không tương thích: '+table.name)
hasher=PasswordHasher()
with Session(engine) as db,db.begin():
    u=db.scalar(select(User).where(User.email==email))
    if u:
        try:ok=hasher.verify(u.password_hash,pwd)
        except (VerificationError,InvalidHashError):ok=False
        if not ok or u.role!='landlord':raise SystemExit('Tài khoản demo tồn tại với thông tin khác.')
    else:
        if getpass.getpass('Nhập lại mật khẩu: ')!=pwd:raise SystemExit('Mật khẩu không khớp.')
        u=User(full_name='Landlord US25 Demo',email=email,role='landlord',password_hash=hasher.hash(pwd));db.add(u);db.flush()
    prop=db.scalar(select(Property).where(Property.owner_id==u.id,Property.name=='MiniStay Dashboard Demo'))
    if not prop:prop=Property(owner_id=u.id,name='MiniStay Dashboard Demo',address='Demo',electricity_unit_price=3500,water_unit_price=15000,service_unit_price=0);db.add(prop);db.flush()
    rooms=[]
    for number,status in [('D01','occupied'),('D02','available'),('D03','maintenance')]:
        room=db.scalar(select(Room).where(Room.property_id==prop.id,Room.room_number==number))
        if not room:room=Room(property_id=prop.id,room_number=number,base_rent=1000000,status=status);db.add(room);db.flush()
        rooms.append(room)
    tenant=db.scalar(select(TenantProfile).where(TenantProfile.id_number=='000000250027'))
    if tenant and tenant.landlord_id!=u.id:raise SystemExit('Mã hồ sơ demo đã thuộc người khác.')
    if not tenant:tenant=TenantProfile(landlord_id=u.id,created_by=u.id,full_name='Người thuê Demo',phone='0900002527',id_number='000000250027');db.add(tenant);db.flush()
    contract=db.scalar(select(Contract).where(Contract.room_id==rooms[0].id,Contract.tenant_id==tenant.id))
    if not contract:contract=Contract(room_id=rooms[0].id,tenant_id=tenant.id,created_by=u.id,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=180),deposit=0,monthly_rent=1000000,status='active');db.add(contract);db.flush()
    period=date.today().strftime('%Y-%m');invoice=db.scalar(select(Invoice).where(Invoice.contract_id==contract.id,Invoice.period==period))
    if not invoice:
        db.add(InvoiceMonth(room_id=rooms[0].id,period=period));invoice=Invoice(contract_id=contract.id,period=period,rent_amount=1000000,utility_amount=0,total_amount=1000000,status='partially_paid');db.add(invoice);db.flush();db.add(Payment(invoice_id=invoice.id,amount=300000,method='cash',recorded_by=u.id,paid_at=datetime.now()))
    for period,status,paid,due in [('2001-01','unpaid',0,date.today()+timedelta(days=5)),('2001-02','paid',1000000,date.today()-timedelta(days=2)),('2001-03','partially_paid',400000,date.today()-timedelta(days=1))]:
        existing=db.scalar(select(Invoice).where(Invoice.contract_id==contract.id,Invoice.period==period))
        if existing is None:
            example=Invoice(contract_id=contract.id,period=period,rent_amount=1000000,utility_amount=0,total_amount=1000000,status=status,due_date=due);db.add(example);db.flush()
            db.add(InvoiceDueDateHistory(invoice_id=example.id,new_due_date=due,reason='Demo agreement',changed_by=u.id))
            if paid:db.add(Payment(invoice_id=example.id,amount=paid,method='cash',recorded_by=u.id,paid_at=datetime.now()))
    for kind,previous,current in [('electricity',100,150),('water',10,16)]:
        current_period=date.today().strftime('%Y-%m')
        if not db.scalar(select(UtilityReading).where(UtilityReading.room_id==rooms[0].id,UtilityReading.period==current_period,UtilityReading.utility_type==kind)):
            db.add(UtilityReading(room_id=rooms[0].id,period=current_period,utility_type=kind,previous_reading=previous,current_reading=current,recorded_by=u.id))
print('Email demo:',email,'| Khu trọ: MiniStay Dashboard Demo')
engine.dispose()
