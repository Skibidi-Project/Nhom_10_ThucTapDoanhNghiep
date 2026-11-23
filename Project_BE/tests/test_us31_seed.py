from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from seed_us31 import EMAIL, demo_engine, seed
from app.db.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.boarding import Property, Room, TenantProfile, Contract, UtilityReading

PASSWORD = "Demo-US31-test!"


@pytest.fixture
def engine(tmp_path):
    result = demo_engine(tmp_path / "demo.db")
    yield result
    result.dispose()


def counts(engine):
    with Session(engine) as db:
        return [db.scalar(select(func.count()).select_from(model))
                for model in (Property, Room, TenantProfile, Contract, UtilityReading)]


def test_required_data_and_meter_continuity(engine):
    assert seed(engine, date(2026, 1, 1), PASSWORD)
    assert counts(engine) == [2, 5, 3, 3, 20]
    with Session(engine) as db:
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
        for room in db.scalars(select(Room)):
            for utility in ("electricity", "water"):
                readings = list(db.scalars(select(UtilityReading).where(
                    UtilityReading.room_id == room.id,
                    UtilityReading.utility_type == utility,
                ).order_by(UtilityReading.period)))
                assert [r.period for r in readings] == ["2025-12", "2026-01"]
                assert readings[0].current_reading == readings[1].previous_reading
                assert all(r.current_reading >= r.previous_reading for r in readings)
                if room.status == "available":
                    assert all(r.current_reading == r.previous_reading for r in readings)


def test_rerun_preserves_edits_and_password(engine):
    seed(engine, date(2026, 11, 1), PASSWORD)
    with Session(engine) as db, db.begin():
        owner = db.scalar(select(User))
        original_hash = owner.password_hash
        owner.full_name = "Edited demo"
    assert not seed(engine, date(2027, 1, 1), "Another-password!")
    assert counts(engine) == [2, 5, 3, 3, 20]
    with Session(engine) as db:
        owner = db.scalar(select(User))
        assert owner.full_name == "Edited demo"
        assert owner.password_hash == original_hash


def test_refuses_database_with_other_data(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add(User(full_name="Existing", email="existing@example.com",
                    role="tenant", password_hash="untouched"))
    with pytest.raises(ValueError, match="dữ liệu khác"):
        seed(engine, date(2026, 11, 1), PASSWORD)
    assert counts(engine) == [0, 0, 0, 0, 0]


def test_failed_seed_rolls_back_all_rows(engine):
    def fail_insert(*args):
        raise RuntimeError("Simulated insert failure")
    event.listen(UtilityReading, "before_insert", fail_insert)
    try:
        with pytest.raises(RuntimeError, match="Simulated"):
            seed(engine, date(2026, 11, 1), PASSWORD)
    finally:
        event.remove(UtilityReading, "before_insert", fail_insert)
    assert counts(engine) == [0, 0, 0, 0, 0]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
    assert seed(engine, date(2026, 11, 1), PASSWORD)


def test_login_and_invoice_for_both_months(engine):
    seed(engine, date(2026, 11, 1), PASSWORD)
    def session_override():
        with Session(engine) as db:
            yield db
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = session_override
    client = TestClient(app)
    try:
        login = client.post("/api/auth/login", json={"identifier": EMAIL, "password": PASSWORD})
        assert login.status_code == 200, login.text
        headers = {"Authorization": "Bearer " + login.json()["access_token"]}
        response = client.get("/api/contracts", headers=headers)
        assert response.status_code == 200, response.text
        contracts = response.json()
        assert len(contracts) == 3
        for contract in contracts:
            for period in ("2026-10", "2026-11"):
                response = client.post(f"/api/contracts/{contract['id']}/invoices",
                                       headers=headers, json={"period": period})
                assert response.status_code == 201, response.text
                invoice = response.json()
                assert invoice["utility_amount"] == 50 * 3500 + 5 * 15000
                assert invoice["total_amount"] == contract["monthly_rent"] + 250000
        assert client.post(f"/api/contracts/{contracts[0]['id']}/invoices",
                           headers=headers, json={"period": "2026-11"}).status_code == 409
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
