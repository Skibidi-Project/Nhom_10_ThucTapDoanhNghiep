"""Isolated local US-19 demo. Never connects to the application's database."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from argon2 import PasswordHasher
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from app.db.database import Base, get_db, engine as application_engine
from app.models.boarding import Property, PropertyManager, Room, UtilityReading
from app.models.user import User
from app.routers import auth, users, properties, billing

DATA = ROOT / ".us19-demo"
DEMO_PASSWORD = "DemoOnly!2026"  # Public synthetic fixture, never a real credential.


@event.listens_for(application_engine, "do_connect")
def forbid_application_database(*_):
    raise RuntimeError("The demo must never connect to the application's database.")


def prepare_database():
    DATA.mkdir(exist_ok=True)
    (DATA / ".gitignore").write_text("*\n", encoding="utf-8")
    path = DATA / "demo.sqlite3"
    marker = DATA / "synthetic-demo-only"
    if path.exists() and not marker.exists():
        raise RuntimeError("Existing SQLite file is not marked as synthetic; refusing writes.")
    marker.write_text("US19 synthetic demo data only\n", encoding="utf-8")
    engine = create_engine("sqlite:///" + path.as_posix(), connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            hashed = PasswordHasher().hash(DEMO_PASSWORD)
            accounts = [(1,"landlord","Chủ trọ Demo","landlord@example.com"),
                        (2,"landlord","Chủ trọ khác","other@example.com"),
                        (3,"manager","Quản lý Demo","manager@example.com"),
                        (4,"tenant","Khách thuê Demo","tenant@example.com"),
                        (5,"manager","Quản lý khác","outsider@example.com"),
                        (6,"admin","Admin Demo","admin@example.com")]
            for uid,role,name,email in accounts:
                db.add(User(id=uid,full_name=name,email=email,phone=f"090000000{uid}",password_hash=hashed,role=role))
            db.flush()
            db.add_all([Property(id=1,owner_id=1,name="MiniStay Garden",address="Địa chỉ mẫu"),
                        Property(id=2,owner_id=2,name="Cơ sở khác",address="Địa chỉ mẫu")])
            db.flush()
            db.add_all([Room(id=1,property_id=1,room_number="A101",base_rent=3500000),
                        Room(id=2,property_id=2,room_number="B201",base_rent=3000000),
                        Room(id=3,property_id=1,room_number="A102",base_rent=3500000)])
            db.add_all([PropertyManager(property_id=1,user_id=3),PropertyManager(property_id=2,user_id=5)])
            db.flush()
            for kind,period,previous,current in [
                ("electricity","2026-01",1000,1120),("electricity","2026-02",1120,1255),
                ("water","2026-01",100,112),("water","2026-02",112,126)]:
                db.add(UtilityReading(room_id=1,utility_type=kind,period=period,previous_reading=previous,current_reading=current,recorded_by=1))
            db.commit()
    return engine,sessions


@asynccontextmanager
async def lifespan(app):
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
    engine,sessions = prepare_database()
    def demo_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = demo_db
    try:
        yield
    finally:
        engine.dispose()
        app.dependency_overrides.clear()


app = FastAPI(title="MiniStay US-19 — SQLite Demo", lifespan=lifespan)
for router in [auth.router,users.router,properties.router,properties.room_router,billing.reading_router]:
    app.include_router(router)
app.mount("/register",StaticFiles(directory=ROOT / "register",html=True),name="register")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=8019,access_log=False)
