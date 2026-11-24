from datetime import date, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.boarding import (
    Property,
    Room,
    TenantProfile,
    Contract,
    Invoice,
    ContractRenewalHistory,
)
from app.core.security import create_access_token


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, expire_on_commit=False)
    with Session.begin() as db:
        users = [
            User(full_name=x, email=x + "@example.com", role=role, password_hash="x")
            for x, role in [
                ("owner", "landlord"),
                ("other", "landlord"),
                ("manager", "manager"),
                ("tenant", "tenant"),
            ]
        ]
        db.add_all(users)
        db.flush()
        prop = Property(owner_id=users[0].id, name="Khu A", address="A")
        db.add(prop)
        db.flush()
        room = Room(
            property_id=prop.id, room_number="101", base_rent=1000, status="occupied"
        )
        db.add(room)
        db.flush()
        tenant = TenantProfile(
            landlord_id=users[0].id,
            created_by=users[0].id,
            full_name="Nguyen Van A",
            phone="0900000000",
            id_number="123456789012",
        )
        db.add(tenant)
        db.flush()
        contract = Contract(
            room_id=room.id,
            tenant_id=tenant.id,
            created_by=users[0].id,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=30),
            monthly_rent=1000,
            deposit=0,
            status="active",
        )
        db.add(contract)
        db.flush()
        cid = contract.id
        pid = prop.id
        headers = [
            {"Authorization": "Bearer " + create_access_token(u.id)} for u in users
        ]

    def dep():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = dep
    yield TestClient(app), headers, cid, pid
    app.dependency_overrides.clear()
    engine.dispose()


def _headers_owner(headers):
    return headers[0]


def test_renew_success(env):
    c, headers, cid, _ = env
    new_end = (date.today() + timedelta(days=400)).isoformat()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["end_date"] == new_end
    assert body["monthly_rent"] == 1000
    assert body["status"] == "active"

    rh = c.get(f"/api/contracts/{cid}/renewals", headers=_headers_owner(headers))
    assert rh.status_code == 200
    history = rh.json()
    assert len(history) == 1
    assert history[0]["previous_monthly_rent"] == 1000
    assert history[0]["new_monthly_rent"] == 1000
    assert history[0]["renewed_by_name"] == "owner"


def test_renew_multiple_times_save_history(env):
    c, headers, cid, _ = env
    for i in range(3):
        new_end = (date.today() + timedelta(days=30 + 365 * (i + 1))).isoformat()
        r = c.post(
            f"/api/contracts/{cid}/renew",
            headers=_headers_owner(headers),
            json={"new_end_date": new_end},
        )
        assert r.status_code == 200, r.text
    rh = c.get(f"/api/contracts/{cid}/renewals", headers=_headers_owner(headers)).json()
    assert len(rh) == 3
    ends = [item["new_end_date"] for item in rh]
    assert len(set(ends)) == 3


def test_renew_keep_rent(env):
    c, headers, cid, _ = env
    new_end = (date.today() + timedelta(days=400)).isoformat()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end},
    )
    assert r.status_code == 200
    assert r.json()["monthly_rent"] == 1000
    hist = c.get(f"/api/contracts/{cid}/renewals", headers=_headers_owner(headers)).json()[0]
    assert hist["previous_monthly_rent"] == 1000
    assert hist["new_monthly_rent"] == 1000


def test_renew_change_rent(env):
    c, headers, cid, _ = env
    new_end = (date.today() + timedelta(days=400)).isoformat()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end, "new_monthly_rent": 1500},
    )
    assert r.status_code == 200
    assert r.json()["monthly_rent"] == 1500
    hist = c.get(f"/api/contracts/{cid}/renewals", headers=_headers_owner(headers)).json()[0]
    assert hist["previous_monthly_rent"] == 1000
    assert hist["new_monthly_rent"] == 1500



def test_renew_invalid_end_date(env):
    c, headers, cid, _ = env
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": date.today().isoformat()},
    )
    assert r.status_code == 409, r.text


def test_renew_respects_10_year_cap(env):
    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    contract = db.get(Contract, cid)
    contract.start_date = date(2020, 1, 15)
    contract.end_date = date(2026, 1, 14)
    db.commit()
    dep.close()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": "2031-01-15"},
    )
    assert r.status_code == 409, r.text


def test_renew_expired_contract(env):
    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    contract = db.get(Contract, cid)
    contract.status = "expired"
    contract.end_date = date.today() - timedelta(days=5)
    db.commit()
    dep.close()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": (date.today() + timedelta(days=400)).isoformat()},
    )
    assert r.status_code == 409, r.text


def test_renew_pending_liquidation(env):
    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    contract = db.get(Contract, cid)
    contract.status = "pending_liquidation"
    db.commit()
    dep.close()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": (date.today() + timedelta(days=400)).isoformat()},
    )
    assert r.status_code == 409, r.text



def test_renew_forbidden_other_landlord(env):
    c, headers, cid, _ = env
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=headers[1],
        json={"new_end_date": (date.today() + timedelta(days=400)).isoformat()},
    )
    assert r.status_code == 403, r.text


def test_renew_blocks_overlap(env):
    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    contract = db.get(Contract, cid)
    room_id = contract.room_id
    other = Contract(
        room_id=room_id,
        tenant_id=contract.tenant_id,
        created_by=contract.created_by,
        start_date=date.today() + timedelta(days=100),
        end_date=date.today() + timedelta(days=200),
        monthly_rent=100,
        deposit=0,
        status="active",
    )
    db.add(other)
    db.commit()
    dep.close()
    new_end = (date.today() + timedelta(days=150)).isoformat()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end},
    )
    assert r.status_code == 409, r.text


def test_renew_rollback_on_history_failure(env, monkeypatch):
    from sqlalchemy.orm import Session

    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    original_end = db.get(Contract, cid).end_date
    dep.close()

    def fail_commit(self):
        raise SQLAlchemyError("simulated failure")

    with monkeypatch.context() as m:
        m.setattr(Session, "commit", fail_commit)
        r = c.post(
            f"/api/contracts/{cid}/renew",
            headers=_headers_owner(headers),
            json={"new_end_date": (date.today() + timedelta(days=400)).isoformat()},
        )
        assert r.status_code == 503, r.text

    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    contract = db.get(Contract, cid)
    assert contract.end_date == original_end
    assert db.scalars(select(ContractRenewalHistory)).all() == []
    dep.close()


def test_invoices_and_payments_unchanged(env):
    c, headers, cid, _ = env
    dep = app.dependency_overrides[get_db]()
    db = next(dep)
    invoice = Invoice(
        contract_id=cid,
        period=date.today().strftime("%Y-%m"),
        rent_amount=1000,
        utility_amount=0,
        total_amount=1000,
        status="unpaid",
    )
    db.add(invoice)
    db.flush()
    iid = invoice.id
    db.commit()
    dep.close()

    new_end = (date.today() + timedelta(days=400)).isoformat()
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end, "new_monthly_rent": 2000},
    )
    assert r.status_code == 200

    inv = c.get(f"/api/invoices/{iid}", headers=_headers_owner(headers)).json()
    assert inv["rent_amount"] == 1000
    assert inv["total_amount"] == 1000


def test_renewed_contract_not_reverted_by_lifecycle(env):
    c, headers, cid, _ = env
    new_end = (date.today() + timedelta(days=400)).isoformat()
    c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={"new_end_date": new_end},
    )
    contracts = c.get("/api/contracts", headers=_headers_owner(headers)).json()
    items = contracts if isinstance(contracts, list) else contracts["items"]
    updated = next(x for x in items if x["id"] == cid)
    assert updated["status"] == "active"
    assert updated["end_date"] == new_end


def test_renew_invalid_payment_cycle(env):
    c, headers, cid, _ = env
    r = c.post(
        f"/api/contracts/{cid}/renew",
        headers=_headers_owner(headers),
        json={
            "new_end_date": (date.today() + timedelta(days=400)).isoformat(),
            "new_payment_cycle_months": 5,
        },
    )
    assert r.status_code == 422, r.text

