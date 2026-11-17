"""Local-only US-12 demo using existing routers, authentication and a separate SQLite DB."""
from contextlib import asynccontextmanager
from datetime import date, timedelta
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from argon2 import PasswordHasher
from app.db.database import Base, get_db, engine as application_engine
from app.models.boarding import Contract, Property, PropertyManager, Room, TenantProfile
from app.models.tenant_member import TenantMember
from app.models.user import User
from app.routers import auth, users, contracts, tenants, tenant_classification, properties, billing

DATA = ROOT / ".us12-demo"
DEMO_PASSWORD = "DemoOnly!2026"  # Public synthetic demo accounts, never a real credential.


@event.listens_for(application_engine, "do_connect")
def forbid_application_database(*_):
    raise RuntimeError("The demo must never connect to the application's database.")


def prepare_database():
    DATA.mkdir(exist_ok=True)
    (DATA / ".gitignore").write_text("*\n", encoding="utf-8")
    path = DATA / "demo.sqlite3"
    marker = DATA / "synthetic-demo-only"
    if path.exists() and not marker.exists():
        raise RuntimeError("Existing database is not marked as synthetic demo data; refusing writes.")
    marker.write_text("US12 synthetic data only\n", encoding="utf-8")
    demo_engine = create_engine("sqlite:///" + path.as_posix(), connect_args={"check_same_thread": False})
    @event.listens_for(demo_engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(demo_engine)
    sessions = sessionmaker(bind=demo_engine, autoflush=False)
    with sessions() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            hashed = PasswordHasher().hash(DEMO_PASSWORD)
            for uid, role, name, email in [
                (1,"landlord","Chủ trọ Demo","landlord@example.com"),
                (2,"landlord","Chủ trọ khác","other@example.com"),
                (3,"manager","Quản lý Demo","manager@example.com"),
                (4,"tenant","Khách thuê Demo","tenant@example.com"),
                (5,"manager","Quản lý khác","outsider@example.com"),
            ]:
                db.add(User(id=uid, full_name=name, email=email, phone=f"090000000{uid}", password_hash=hashed, role=role))
            db.flush()
            db.add_all([Property(id=1,owner_id=1,name="MiniStay Garden",address="Địa chỉ mẫu — dữ liệu demo"),Property(id=2,owner_id=2,name="Cơ sở khác",address="Địa chỉ mẫu")])
            db.flush()
            db.add_all([Room(id=1,property_id=1,room_number="A101",base_rent=3500000),Room(id=2,property_id=2,room_number="B201",base_rent=3000000)])
            db.add_all([PropertyManager(property_id=1,user_id=3),PropertyManager(property_id=2,user_id=5)])
            for tid, name in [(1,"Nguyễn Minh An"),(2,"Trần Thu Hà"),(3,"Lê Hoàng Nam"),(4,"Phạm Ngọc Linh")]:
                db.add(TenantProfile(id=tid,landlord_id=1,created_by=1,full_name=name,phone=f"091000000{tid}",id_number=f"00000000000{tid}"))
            db.flush()
            for cid, status, end in [(1,"active",365),(2,"expired",-1)]:
                db.add(Contract(id=cid,room_id=1,tenant_id=1,created_by=1,start_date=date.today()-timedelta(days=30),end_date=date.today()+timedelta(days=end),monthly_rent=3500000,status=status))
            db.flush()
            db.add(TenantMember(contract_id=1,tenant_id=2))
            db.commit()
    return demo_engine, sessions


@asynccontextmanager
async def lifespan(app):
    # Ephemeral signing key affects only this demo process; existing auth code is unchanged.
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
    demo_engine, sessions = prepare_database()
    def demo_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = demo_db
    try:
        yield
    finally:
        demo_engine.dispose()
        app.dependency_overrides.clear()


app = FastAPI(title="MiniStay US-12 — SQLite Demo", lifespan=lifespan)
for router in [auth.router,users.router,contracts.router,tenants.router,tenant_classification.router,
               properties.router,properties.room_router,billing.invoice_router,billing.reading_router]:
    app.include_router(router)
app.mount("/register", StaticFiles(directory=ROOT / "register", html=True), name="register")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8012, access_log=False)
