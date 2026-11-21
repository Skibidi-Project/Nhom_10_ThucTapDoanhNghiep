"""Copy only local products_db schema into an isolated test DB and seed fake rows."""
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

url = make_url(os.environ['MINISTAY_MYSQL_SOURCE_URL'])
if url.get_backend_name() != 'mysql' or url.host not in ('localhost', '127.0.0.1') or (url.port or 3306) != 3306 or url.database != 'products_db':
    raise SystemExit('Refusing unexpected source')
name = 'ministay_old_schema_test_' + uuid.uuid4().hex[:12]
source, admin = create_engine(url), create_engine(url.set(database=None))
with admin.begin() as connection:
    connection.exec_driver_sql(f'CREATE DATABASE `{name}` CHARACTER SET utf8mb4')
target = create_engine(url.set(database=name))
with source.connect() as src, target.begin() as dst:
    dst.exec_driver_sql('SET FOREIGN_KEY_CHECKS=0')
    for table in inspect(src).get_table_names():
        if not all(char.isalnum() or char == '_' for char in table):
            raise SystemExit('Unexpected identifier')
        ddl = src.exec_driver_sql(f'SHOW CREATE TABLE `{table}`').one()[1]
        dst.exec_driver_sql(ddl)
    dst.exec_driver_sql('SET FOREIGN_KEY_CHECKS=1')
    # Only synthetic data is inserted; no production records are copied.
    for statement in (
        "INSERT INTO users(id,full_name,email,password_hash,role) VALUES(1,'Test','migration@example.invalid','x','landlord')",
        "INSERT INTO properties(id,owner_id,name,address,electricity_unit_price,water_unit_price,service_unit_price,created_at) VALUES(1,1,'Test','Test',1,1,1,NOW())",
        "INSERT INTO rooms(id,property_id,room_number,base_rent,status) VALUES(1,1,'T',100,'occupied')",
        "INSERT INTO tenants(id,landlord_id,created_by,full_name,phone,id_number) VALUES(1,1,1,'Test','0900000000','123456789012')",
        "INSERT INTO rental_contracts(id,room_id,tenant_id,created_by,start_date,end_date,deposit,monthly_rent,status) VALUES(1,1,1,1,'2020-01-01','2030-12-31',0,100,'active')",
        "INSERT INTO invoices(id,contract_id,period,rent_amount,utility_amount,total_amount,status,created_at) VALUES(1,1,'2025-01',100,0,100,'partially_paid',NOW())",
        "INSERT INTO payments(id,invoice_id,amount,method,recorded_by,paid_at) VALUES(1,1,30,'cash',1,NOW())",
    ):
        dst.execute(text(statement))
    before_invoice = dst.execute(text('SELECT id,contract_id,period,rent_amount,utility_amount,total_amount,status,created_at FROM invoices')).all()
    before_payment = dst.execute(text('SELECT id,invoice_id,amount,method,recorded_by,paid_at FROM payments')).all()
env = os.environ.copy()
env['DATABASE_URL'] = url.set(database=name).render_as_string(hide_password=False)
env['JWT_SECRET'] = secrets.token_urlsafe(48)
runner = Path(__file__).resolve().parents[1] / 'migrations/apply_mysql_migrations.py'
command = [sys.executable, str(runner), '--confirm-database', name]
for args in ([], ['--execute'], ['--execute']):
    subprocess.run(command + args, env=env, check=True)
with target.connect() as connection:
    assert connection.execute(text('SELECT id,contract_id,period,rent_amount,utility_amount,total_amount,status,created_at FROM invoices')).all() == before_invoice
    assert connection.execute(text('SELECT id,invoice_id,amount,method,recorded_by,paid_at FROM payments')).all() == before_payment
    assert connection.scalar(text('SELECT due_date FROM invoices WHERE id=1')) is None
    assert connection.execute(text('SELECT note,idempotency_key,request_fingerprint FROM payments WHERE id=1')).one() == (None, None, None)
    assert connection.scalar(text('SELECT COUNT(*) FROM utility_price_history')) == 0
print('PASS synthetic historic invoice/payment preserved; no dates or prices fabricated:', name)
