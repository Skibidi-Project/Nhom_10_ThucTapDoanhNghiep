import os, secrets, subprocess, sys, tempfile, time, urllib.request
os.environ.setdefault('JWT_SECRET',secrets.token_urlsafe(48))
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
db_path=Path(tempfile.gettempdir())/('ministay_business_e2e_'+secrets.token_hex(8)+'.sqlite3')
os.environ['DATABASE_URL']='sqlite:///'+db_path.as_posix()
from sqlalchemy.orm import Session
from app.db.database import Base,engine
from app.db.reading_revision import reading_revision
from app.db.invoice_snapshot import invoice_snapshot
from app.db.settlement_trial import metadata as trial_metadata
import app.models,app.models.room_type
from app.models.user import User
from app.models.boarding import Property,Room,TenantProfile,Contract
from app.services.user_service import password_hasher
assert engine.dialect.name=='sqlite' and db_path.name.startswith('ministay_business_e2e_')
Base.metadata.create_all(engine);reading_revision.create(engine);invoice_snapshot.create(engine)
final_trial = os.getenv('MINISTAY_FINAL_E2E') == '1'
if final_trial:
    os.environ['MINISTAY_US16_TRIAL']='1'
    trial_metadata.create_all(engine)
email='e2e-'+secrets.token_hex(6)+'@example.com';password=secrets.token_urlsafe(20)
with Session(engine) as db, db.begin():
    u=User(full_name='Test Owner',email=email,password_hash=password_hasher.hash(password),role='landlord');db.add(u);db.flush()
    p=Property(owner_id=u.id,name='Test',address='Test',electricity_unit_price=10,water_unit_price=20,service_unit_price=0);db.add(p);db.flush()
    r=Room(property_id=p.id,room_number='TEST',base_rent=100,status='occupied');t=TenantProfile(landlord_id=u.id,created_by=u.id,full_name='Tenant',phone='0900000000',id_number='123456789012');db.add_all([r,t]);db.flush()
    db.add(Contract(room_id=r.id,tenant_id=t.id,created_by=u.id,start_date=date.today().replace(day=1) if final_trial else date.today()-timedelta(days=1),end_date=date.today()+timedelta(days=30),deposit=100 if final_trial else 0,deposit_status='held' if final_trial else 'unpaid',monthly_rent=100,status='active'))
env=os.environ.copy();env['MINISTAY_E2E_EMAIL']=email;env['MINISTAY_E2E_PASSWORD']=password;env['PYTHONDONTWRITEBYTECODE']='1'
server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18342'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    for _ in range(100):
        try:
            with urllib.request.urlopen('http://127.0.0.1:18342/openapi.json',timeout=1) as r:
                if r.status==200:break
        except OSError:time.sleep(.1)
    else:raise RuntimeError('Test server did not start')
    raise SystemExit(subprocess.call(['node','tests/e2e_final_trial.cjs' if final_trial else 'tests/e2e_business.cjs'],env=env))
finally:
    server.terminate();server.wait(timeout=10)
