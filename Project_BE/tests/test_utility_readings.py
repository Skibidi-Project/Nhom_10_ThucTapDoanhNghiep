import pytest
from sqlalchemy import select

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.db.database import Base, get_db
from app.models.boarding import Property, PropertyManager, Room
from app.core.security import create_access_token
from app.models.user import User
from app.routers.billing import reading_router
from app.models.boarding import Invoice, UtilityReading


def headers(user_id):
    return {"Authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def readings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "us19-test-only-secret-with-at-least-32-bytes")
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            for user_id, role in [(1,"landlord"),(2,"landlord"),(3,"manager"),
                                  (4,"tenant"),(5,"manager"),(6,"admin")]:
                db.add(User(id=user_id, full_name=f"User {user_id}",
                            email=f"u{user_id}@example.com", phone=f"090000000{user_id}",
                            password_hash="unused-test-hash", role=role))
            db.flush()
            db.add_all([Property(id=1,owner_id=1,name="A",address="A"),
                        Property(id=2,owner_id=1,name="B",address="B")])
            db.flush()
            db.add_all([Room(id=1,property_id=1,room_number="101",base_rent=100),
                        Room(id=2,property_id=2,room_number="201",base_rent=100)])
            db.add_all([PropertyManager(property_id=1,user_id=3),
                        PropertyManager(property_id=2,user_id=5)])
            db.commit()
            app = FastAPI()
            app.include_router(reading_router)
            app.dependency_overrides[get_db] = lambda: db
            with TestClient(app) as client:
                yield client, db
    finally:
        engine.dispose()


def record(client,period="2026-01",previous=10,current=20,kind="electricity",actor=1):
    return client.post("/api/rooms/1/readings",headers=headers(actor),json={
        "period":period,"previous_reading":previous,"current_reading":current,"utility_type":kind})


def test_continuity_independent_and_gaps(readings):
    client, db = readings
    assert record(client).status_code == 201
    assert record(client,"2026-03",20,30).status_code == 201
    assert record(client,"2026-01",100,120,"water").status_code == 201
    assert record(client,"2026-03",120,120,"water").status_code == 201
    assert record(client,"2026-01",0,1,"service").status_code == 201
    assert record(client,"2025-12",0,1,"service").status_code == 201
    assert len(client.get("/api/rooms/1/readings",headers=headers(1)).json()) == 6
    assert db.scalars(select(Invoice)).all() == []


@pytest.mark.parametrize("period,previous,current",[("2026-01",10,20),("2025-12",20,30),("2026-02",19,30)])
def test_reject_duplicate_backdated_and_broken_chain(readings,period,previous,current):
    client, db = readings
    assert record(client).status_code == 201
    assert record(client,period,previous,current).status_code == 409
    rows = db.scalars(select(UtilityReading)).all()
    assert len(rows) == 1 and rows[0].current_reading == 20


@pytest.mark.parametrize("period,previous,current",[("2026-13",0,1),("2026-01",-1,1),("2026-01",10,9)])
def test_reading_validation(readings,period,previous,current):
    client,_ = readings
    assert record(client,period,previous,current).status_code == 422


@pytest.mark.parametrize("actor,expected",[(1,201),(2,403),(3,201),(4,403),(5,403),(6,403)])
def test_reading_scope(readings,actor,expected):
    client,_ = readings
    assert record(client,actor=actor).status_code == expected


def test_reading_missing_room_and_auth(readings):
    client,_ = readings
    assert client.get("/api/rooms/999/readings",headers=headers(1)).status_code == 404
    assert client.get("/api/rooms/1/readings").status_code == 401
