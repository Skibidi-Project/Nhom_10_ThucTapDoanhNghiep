import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db import database
from app.main import app
from app.models.boarding import (
    Contract,
    Property,
    PropertyManager,
    PropertyServicePrice,
    Room,
    ServiceAssignment,
    TenantProfile,
    User,
)

pytestmark = pytest.mark.us29


@pytest.fixture(autouse=True)
def reset_database():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    yield
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()


def make_user(db_session, role, full_name, email, phone):
    user = User(full_name=full_name, email=email, phone=phone, password_hash="hash", role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_property(db_session, owner_id, name="Khu demo", electricity=3000, water=20000, service=0):
    prop = Property(
        owner_id=owner_id,
        name=name,
        address="??a ch? demo",
        electricity_unit_price=electricity,
        water_unit_price=water,
        service_unit_price=service,
    )
    db_session.add(prop)
    db_session.commit()
    db_session.refresh(prop)
    return prop


def make_room(db_session, property_id, room_number="P101"):
    room = Room(property_id=property_id, room_number=room_number, area_sqm=25.5, base_rent=5000000, status="available")
    db_session.add(room)
    db_session.commit()
    db_session.refresh(room)
    return room


def auth_header(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def service_prices_map(db_session, property_id):
    rows = db_session.scalars(
        select(PropertyServicePrice).where(PropertyServicePrice.property_id == property_id)
    )
    return {row.service_code: row for row in rows}


from sqlalchemy import select  # noqa: E402


def test_create_property_with_prices_creates_config_rows(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t1@example.com", "0900000001")
    res = client.post(
        "/api/properties",
        json={
            "name": "Khu A",
            "address": "123 A",
            "electricity_unit_price": 3000,
            "water_unit_price": 20000,
            "service_unit_price": 0,
        },
        headers=auth_header(landlord),
    )
    assert res.status_code == 201, res.text
    prop_id = res.json()["id"]

    db_session.expire_all()
    prices = service_prices_map(db_session, prop_id)
    assert set(prices) == {"electricity", "water"}, prices
    assert prices["electricity"].billing_unit == "kwh"
    assert prices["electricity"].unit_price == 3000
    assert prices["water"].billing_unit == "m3"
    assert prices["water"].unit_price == 20000

    db_session.expire_all()
    prop = db_session.get(Property, prop_id)
    assert prop.electricity_unit_price == 3000
    assert prop.water_unit_price == 20000


def test_create_property_with_zero_prices_creates_no_config(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t2@example.com", "0900000002")
    res = client.post(
        "/api/properties",
        json={
            "name": "Khu B",
            "address": "456 B",
            "electricity_unit_price": 0,
            "water_unit_price": 0,
            "service_unit_price": 0,
        },
        headers=auth_header(landlord),
    )
    assert res.status_code == 201, res.text
    prop_id = res.json()["id"]

    db_session.expire_all()
    prices = service_prices_map(db_session, prop_id)
    assert prices == {}, prices



def test_update_property_prices_updates_column_and_config(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t3@example.com", "0900000003")
    prop = make_property(db_session, landlord.id, electricity=3000, water=20000)

    res = client.put(
        f"/api/properties/{prop.id}",
        json={"electricity_unit_price": 3500, "water_unit_price": 25000},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.electricity_unit_price == 3500
    assert prop.water_unit_price == 25000

    prices = service_prices_map(db_session, prop.id)
    assert prices["electricity"].unit_price == 3500
    assert prices["electricity"].billing_unit == "kwh"
    assert prices["water"].unit_price == 25000
    assert prices["water"].billing_unit == "m3"


def test_update_property_to_zero_removes_config_when_unassigned(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t4@example.com", "0900000004")
    prop = make_property(db_session, landlord.id, electricity=3000, water=20000)

    res = client.put(
        f"/api/properties/{prop.id}",
        json={"electricity_unit_price": 0, "water_unit_price": 0},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.electricity_unit_price == 0
    assert prop.water_unit_price == 0
    assert service_prices_map(db_session, prop.id) == {}


def test_update_property_to_zero_blocked_when_assigned(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t5@example.com", "0900000005")
    prop = make_property(db_session, landlord.id, electricity=3000, water=20000)
    room = make_room(db_session, prop.id, "P1")
    db_session.add(
        ServiceAssignment(
            room_id=room.id,
            service_code="electricity",
            quantity=1,
            assigned_by=landlord.id,
        )
    )
    db_session.commit()

    res = client.put(
        f"/api/properties/{prop.id}",
        json={"name": "Đổi tên", "electricity_unit_price": 0, "water_unit_price": 0},
        headers=auth_header(landlord),
    )
    assert res.status_code == 409, res.text
    assert "giá điện" in res.json()["detail"].lower() or "điện" in res.json()["detail"].lower()

    # Không có thay đổi nào được lưu (cả cột lẫn config).
    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.name == "Khu demo"
    assert prop.electricity_unit_price == 3000
    assert prop.water_unit_price == 20000
    prices = service_prices_map(db_session, prop.id)
    assert prices["electricity"].unit_price == 3000


def test_put_service_price_electricity_updates_column(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t6@example.com", "0900000006")
    prop = make_property(db_session, landlord.id, electricity=3000, water=0)

    res = client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 4000},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.electricity_unit_price == 4000


def test_put_service_price_water_m3_updates_column(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t7@example.com", "0900000007")
    prop = make_property(db_session, landlord.id, electricity=0, water=0)

    res = client.put(
        f"/api/properties/{prop.id}/service-prices/water",
        json={"billing_unit": "m3", "unit_price": 15000},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.water_unit_price == 15000


def test_put_service_price_water_person_month_does_not_change_column(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t8@example.com", "0900000008")
    prop = make_property(db_session, landlord.id, electricity=0, water=0)

    res = client.put(
        f"/api/properties/{prop.id}/service-prices/water",
        json={"billing_unit": "person_month", "unit_price": 50000},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.water_unit_price == 0  # cột không đổi


def test_update_property_water_when_config_person_month_changes_column_only(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t9@example.com", "0900000009")
    prop = make_property(db_session, landlord.id, electricity=0, water=0)
    client.put(
        f"/api/properties/{prop.id}/service-prices/water",
        json={"billing_unit": "person_month", "unit_price": 50000},
        headers=auth_header(landlord),
    )

    # Sửa giá nước ở cơ sở: cột đổi, config person_month giữ nguyên.
    res = client.put(
        f"/api/properties/{prop.id}",
        json={"water_unit_price": 18000},
        headers=auth_header(landlord),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.water_unit_price == 18000
    row = service_prices_map(db_session, prop.id).get("water")
    assert row is not None
    assert row.billing_unit == "person_month"
    assert row.unit_price == 50000  # config không đổi


def test_delete_service_price_electricity_sets_column_zero(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t10@example.com", "0900000010")
    prop = make_property(db_session, landlord.id, electricity=3000, water=0)
    client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 3000},
        headers=auth_header(landlord),
    )

    res = client.delete(
        f"/api/properties/{prop.id}/service-prices/electricity",
        headers=auth_header(landlord),
    )
    assert res.status_code == 204, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.electricity_unit_price == 0


def test_manager_can_update_service_price_and_column_changes(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t11@example.com", "0900000011")
    manager = make_user(db_session, "manager", "Manager", "t11m@example.com", "0900000012")
    prop = make_property(db_session, landlord.id, electricity=0, water=0)
    db_session.add(PropertyManager(property_id=prop.id, user_id=manager.id))
    db_session.commit()

    res = client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 3300},
        headers=auth_header(manager),
    )
    assert res.status_code == 200, res.text

    db_session.expire_all()
    prop = db_session.get(Property, prop.id)
    assert prop.electricity_unit_price == 3300


def test_forbidden_roles(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "t12@example.com", "0900000013")
    manager = make_user(db_session, "manager", "Manager", "t12m@example.com", "0900000014")
    tenant = make_user(db_session, "tenant", "Tenant", "t12t@example.com", "0900000015")
    prop = make_property(db_session, landlord.id, electricity=3000, water=20000)

    no_token = client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 4000},
    )
    assert no_token.status_code == 401

    tenant_res = client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 4000},
        headers=auth_header(tenant),
    )
    assert tenant_res.status_code == 403

    # Manager không phải PROPERTY_MANAGE không thể sửa cột qua PUT property.
    manager_prop = client.put(
        f"/api/properties/{prop.id}",
        json={"electricity_unit_price": 4000},
        headers=auth_header(manager),
    )
    assert manager_prop.status_code == 403

    # Manager không gán vào khu trọ không thao tác được config.
    other_manager = make_user(db_session, "manager", "Other", "t12o@example.com", "0900000016")
    other_res = client.put(
        f"/api/properties/{prop.id}/service-prices/electricity",
        json={"billing_unit": "kwh", "unit_price": 4000},
        headers=auth_header(other_manager),
    )
    assert other_res.status_code == 403

