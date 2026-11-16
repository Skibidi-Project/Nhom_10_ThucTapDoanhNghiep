"""Ch? d?ng SQLite trong b? nh?; kh?ng ch?y lifespan/init_db c?a app ch?nh."""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.core.deps import get_current_user
from app.models.boarding import Contract, Property, PropertyManager, Room, TenantProfile
from app.models.user import User
from app.routers.tenant_classification import router
from app.routers import tenants, contracts
from app.models.tenant_member import TenantMember


@pytest.fixture
def context():
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i, role in [(1,"landlord"),(2,"landlord"),(3,"manager"),(4,"tenant"),(5,"manager")]:
            db.add(User(id=i, full_name=f"User {i}", email=f"u{i}@example.com",
                        phone=f"090000000{i}", password_hash="test", role=role))
        db.flush()
        db.add_all([Property(id=1,owner_id=1,name="A",address="A"),
                    Property(id=2,owner_id=1,name="B",address="B")])
        db.flush()
        db.add_all([Room(id=1,property_id=1,room_number="101",base_rent=100),
                    Room(id=2,property_id=2,room_number="201",base_rent=100)])
        for i in range(1,5):
            db.add(TenantProfile(id=i,landlord_id=2 if i==4 else 1,created_by=1,
                                full_name=f"Tenant {i}", phone="0900000000",id_number=str(i)))
        db.flush()
        db.add_all([PropertyManager(property_id=1,user_id=3),PropertyManager(property_id=2,user_id=5)])
        db.add(Contract(id=1,room_id=1,tenant_id=1,created_by=1,
                        start_date=date.today(),end_date=date.today()+timedelta(days=30),
                        monthly_rent=100,status="active"))
        db.commit()
        app=FastAPI()
        app.include_router(router)
        app.include_router(tenants.router)
        app.include_router(contracts.router)
        actor={"id":1}
        app.dependency_overrides[get_db]=lambda: db
        app.dependency_overrides[get_current_user]=lambda: db.get(User,actor["id"])
        with TestClient(app) as client:
            yield client,db,actor,app
    engine.dispose()


def test_group_add_remove_and_old_apis(context):
    client,db,_,_=context
    assert client.get("/api/contracts/1/tenant-group").json()["representative"] == {
        "tenant_id":1,"full_name":"Tenant 1","classification":"representative"}
    for tenant_id in (2,3):
        assert client.post("/api/contracts/1/members",json={"tenant_id":tenant_id}).status_code==201
    assert len(client.get("/api/contracts/1/tenant-group").json()["members"])==2
    assert client.get("/api/tenants").status_code==200
    assert client.get("/api/contracts/1").json()["tenant_id"]==1
    assert client.delete("/api/contracts/1/members/2").status_code==204
    assert db.get(TenantProfile,2) is not None
    assert db.get(Contract,1).tenant_id==1
    assert client.delete("/api/contracts/1/members/2").status_code==404
    assert client.delete("/api/contracts/1/members/1").status_code==409


@pytest.mark.parametrize("tenant_id,expected",[(1,409),(4,403),(999,404),(0,422)])
def test_invalid_members(context,tenant_id,expected):
    client,_,_,_=context
    assert client.post("/api/contracts/1/members",json={"tenant_id":tenant_id}).status_code==expected


def test_duplicate(context):
    client,db,_,_=context
    assert client.post("/api/contracts/1/members",json={"tenant_id":2}).status_code==201
    assert client.post("/api/contracts/1/members",json={"tenant_id":2}).status_code==409
    assert len(db.scalars(select(TenantMember)).all())==1


@pytest.mark.parametrize("actor_id,expected",[(1,200),(2,403),(3,200),(4,403),(5,403)])
def test_scope(context,actor_id,expected):
    client,_,actor,_=context
    actor["id"]=actor_id
    assert client.get("/api/contracts/1/tenant-group").status_code==expected
    assert client.post("/api/contracts/1/members",json={"tenant_id":2}).status_code==(201 if expected==200 else expected)
    assert client.delete("/api/contracts/1/members/2").status_code==(204 if expected==200 else expected)


def test_missing_contract_room_and_auth(context):
    client,db,_,app=context
    assert client.get("/api/contracts/999/tenant-group").status_code==404
    assert client.post("/api/contracts/999/members",json={"tenant_id":2}).status_code==404
    assert client.delete("/api/contracts/999/members/2").status_code==404
    contract=db.get(Contract,1)
    contract.room_id=999  # D? li?u h?ng ch? ? session test, kh?ng flush.
    with db.no_autoflush:
        assert client.get("/api/contracts/1/tenant-group").status_code==404
    db.rollback()
    del app.dependency_overrides[get_current_user]
    assert client.get("/api/contracts/1/tenant-group").status_code==401


@pytest.mark.parametrize("status,ended",[("expired",False),("pending_liquidation",False),("active",True)])
def test_history_is_read_only(context,status,ended):
    client,db,_,_=context
    client.post("/api/contracts/1/members",json={"tenant_id":2})
    contract=db.get(Contract,1)
    contract.status=status
    if ended: contract.end_date=date.today()-timedelta(days=1)
    db.commit()
    assert client.get("/api/contracts/1/tenant-group").status_code==200
    assert client.post("/api/contracts/1/members",json={"tenant_id":3}).status_code==409
    assert client.delete("/api/contracts/1/members/2").status_code==409


def test_privilege_injection(context):
    client,_,_,_=context
    assert client.post("/api/contracts/1/members",json={"tenant_id":2,"role":"admin"}).status_code==403
