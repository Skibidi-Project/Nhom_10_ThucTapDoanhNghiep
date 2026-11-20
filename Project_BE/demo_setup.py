"""Create only the dedicated local demo SQLite schema and sample records."""
import getpass
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import inspect, select
from sqlalchemy.engine import make_url

EMAIL = 'landlord.final.demo@example.com'
expected = (Path(tempfile.gettempdir()).resolve() / 'ministay_business_e2e_manual_demo.sqlite3')
url = make_url(os.environ.get('DATABASE_URL', 'sqlite://'))
if (url.get_backend_name() != 'sqlite' or not url.database or
        Path(url.database).resolve() != expected or expected.is_symlink() or
        os.environ.get('MINISTAY_US16_TRIAL') != '1'):
    raise SystemExit('Từ chối: chỉ cho phép SQLite demo cố định trong TEMP.')

from app.db.database import Base, engine
from app.db.reading_revision import reading_revision
from app.db.invoice_snapshot import invoice_snapshot
from app.db.settlement_trial import metadata as trial_metadata
import app.models, app.models.room_type
from app.models.user import User
from app.models.boarding import Property, Room, TenantProfile, Contract
from sqlalchemy.orm import Session

password = getpass.getpass('Nhập mật khẩu tài khoản demo (không hiển thị): ')
if len(password) < 8:
    raise SystemExit('Mật khẩu demo cần ít nhất 8 ký tự.')
hasher = PasswordHasher()
Base.metadata.create_all(engine)
reading_revision.create(engine, checkfirst=True)
invoice_snapshot.create(engine, checkfirst=True)
trial_metadata.create_all(engine, checkfirst=True)
required={'users','properties','rooms','tenants','rental_contracts','utility_readings','invoices','payments','invoice_months','reading_revisions','invoice_snapshots','us16_trial_final_approvals','us16_trial_meter_handovers','us16_trial_settlements','us16_trial_damages','us16_trial_invoice_reviews','us16_trial_receivables','us16_trial_input_revisions'}
if not required.issubset(set(inspect(engine).get_table_names())):
    raise SystemExit('Schema demo thiếu bảng; dừng khởi động.')
inspector=inspect(engine)
for table in list(Base.metadata.sorted_tables)+[reading_revision,invoice_snapshot]+list(trial_metadata.sorted_tables):
    actual={col['name'] for col in inspector.get_columns(table.name)}
    missing={col.name for col in table.columns}-actual
    if missing: raise SystemExit(f'Schema demo không tương thích: {table.name} thiếu cột {sorted(missing)}.')
with Session(engine) as db, db.begin():
    user=db.scalar(select(User).where(User.email==EMAIL))
    if user:
        try: valid=hasher.verify(user.password_hash,password)
        except (VerificationError,InvalidHashError): valid=False
        if not valid or user.role!='landlord': raise SystemExit('Tài khoản demo đã tồn tại với thông tin khác; không tự sửa.')
    else:
        if getpass.getpass('Nhập lại mật khẩu demo: ') != password: raise SystemExit('Mật khẩu nhập lại không khớp.')
        user=User(full_name='Landlord Final Demo',email=EMAIL,role='landlord',password_hash=hasher.hash(password));db.add(user);db.flush()
    prop=db.scalar(select(Property).where(Property.owner_id==user.id,Property.name=='MiniStay Final Demo'))
    if not prop:
        prop=Property(owner_id=user.id,name='MiniStay Final Demo',address='Địa chỉ demo',electricity_unit_price=3500,water_unit_price=15000,service_unit_price=0);db.add(prop);db.flush()
    room=db.scalar(select(Room).where(Room.property_id==prop.id,Room.room_number=='DEMO-01'))
    if not room:
        room=Room(property_id=prop.id,room_number='DEMO-01',base_rent=2000000,status='occupied');db.add(room);db.flush()
    tenant=db.scalar(select(TenantProfile).where(TenantProfile.id_number=='000000160019'))
    if tenant and tenant.landlord_id != user.id: raise SystemExit('Mã hồ sơ demo đã thuộc chủ trọ khác.')
    if not tenant:
        tenant=TenantProfile(landlord_id=user.id,created_by=user.id,full_name='Người thuê Demo',phone='0900001619',id_number='000000160019');db.add(tenant);db.flush()
    contract=db.scalar(select(Contract).where(Contract.room_id==room.id,Contract.tenant_id==tenant.id,Contract.created_by==user.id))
    if not contract:
        contract=Contract(room_id=room.id,tenant_id=tenant.id,created_by=user.id,start_date=date.today().replace(day=1),end_date=date.today()+timedelta(days=180),deposit=2000000,deposit_status='held',monthly_rent=2000000,status='active');db.add(contract);db.flush()
    if contract.status not in ('active','pending_liquidation'):
        print('Lưu ý: hợp đồng demo đã kết thúc; dữ liệu cũ được giữ nguyên.')
print(f'Tài khoản demo: {EMAIL}; khu trọ MiniStay Final Demo; phòng DEMO-01.')
engine.dispose()
