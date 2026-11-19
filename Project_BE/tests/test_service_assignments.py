import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.core.security import create_access_token
from app.db import database
from app.main import app
from app.models.boarding import Contract, Property, PropertyManager, PropertyServicePrice, Room, TenantProfile
from app.models.user import User


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
    db_session.commit(); db_session.refresh(user)
    return user


def make_property(db_session, owner_id, name="Khu demo"):
    prop = Property(owner_id=owner_id, name=name, address="??a ch? demo", electricity_unit_price=3000, water_unit_price=20000, service_unit_price=0)
    db_session.add(prop)
    db_session.commit(); db_session.refresh(prop)
    return prop


def make_service_price(db_session, property_id, service_code, billing_unit, unit_price):
    row = PropertyServicePrice(property_id=property_id, service_code=service_code, billing_unit=billing_unit, unit_price=unit_price)
    db_session.add(row)
    db_session.commit(); db_session.refresh(row)
    return row


def make_room(db_session, property_id, room_number="P101", status="available"):
    room = Room(property_id=property_id, room_number=room_number, area_sqm=25.5, base_rent=5000000, status=status)
    db_session.add(room)
    db_session.commit(); db_session.refresh(room)
    return room


def make_tenant(db_session, landlord_id, name="Tenant A"):
    tenant = TenantProfile(
        landlord_id=landlord_id,
        created_by=landlord_id,
        user_id=None,
        full_name=name,
        phone="0900000003",
        id_number="123456789",
        email=f"{name.lower().replace(' ', '')}@example.com",
    )
    db_session.add(tenant)
    db_session.commit(); db_session.refresh(tenant)
    return tenant


def make_contract(db_session, room_id, tenant_id, created_by, status="active"):
    today = date.today()
    contract = Contract(
        room_id=room_id,
        tenant_id=tenant_id,
        created_by=created_by,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=180),
        deposit=1000000,
        monthly_rent=5000000,
        payment_cycle_months=1,
        status=status,
    )
    db_session.add(contract)
    db_session.commit(); db_session.refresh(contract)
    return contract


def auth_header(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_landlord_manager_can_assign_and_forbidden_roles(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "landlord@example.com", "0900000001")
    manager = make_user(db_session, "manager", "Manager", "manager@example.com", "0900000002")
    tenant_user = make_user(db_session, "tenant", "Tenant", "tenant@example.com", "0900000003")
    other_landlord = make_user(db_session, "landlord", "Other landlord", "other@example.com", "0900000004")

    property_obj = make_property(db_session, landlord.id)
    make_service_price(db_session, property_obj.id, "wifi", "room_month", 50000)
    make_service_price(db_session, property_obj.id, "parking", "vehicle_month", 150000)
    room = make_room(db_session, property_obj.id)

    no_token_prices = client.get(f"/api/properties/{property_obj.id}/service-prices")
    assert no_token_prices.status_code == 401
    cross_property_prices = client.get(
        f"/api/properties/{property_obj.id}/service-prices",
        headers=auth_header(other_landlord),
    )
    assert cross_property_prices.status_code == 403

    res = client.post(
        "/api/service-assignments",
        json={"service_code": "wifi", "room_id": room.id, "quantity": 1},
        headers=auth_header(landlord),
    )
    assert res.status_code == 201, res.text

    db_session.add(PropertyManager(property_id=property_obj.id, user_id=manager.id))
    db_session.commit()
    manager_prices = client.get(
        f"/api/properties/{property_obj.id}/service-prices",
        headers=auth_header(manager),
    )
    assert manager_prices.status_code == 200
    grant = client.post(
        "/api/service-assignments",
        json={"service_code": "parking", "room_id": room.id, "quantity": 2},
        headers=auth_header(manager),
    )
    assert grant.status_code == 201, grant.text

    blocked = client.post(
        "/api/service-assignments",
        json={"service_code": "wifi", "room_id": room.id, "quantity": 1},
        headers=auth_header(other_landlord),
    )
    assert blocked.status_code == 403

    tenant_forbidden = client.post(
        "/api/service-assignments",
        json={"service_code": "wifi", "room_id": room.id, "quantity": 1},
        headers=auth_header(tenant_user),
    )
    assert tenant_forbidden.status_code == 403

    no_token = client.post(
        "/api/service-assignments",
        json={"service_code": "wifi", "room_id": room.id, "quantity": 1},
    )
    assert no_token.status_code == 401


def test_validation_duplicate_and_effective_services(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "landlord2@example.com", "0900000011")
    tenant = make_tenant(db_session, landlord.id)
    prop = make_property(db_session, landlord.id)
    room = make_room(db_session, prop.id, "P202")
    make_service_price(db_session, prop.id, "wifi", "room_month", 50000)
    make_service_price(db_session, prop.id, "parking", "vehicle_month", 150000)
    make_service_price(db_session, prop.id, "electricity", "kwh", 3000)

    first = client.post("/api/service-assignments", json={"service_code": "wifi", "room_id": room.id, "quantity": 1}, headers=auth_header(landlord))
    assert first.status_code == 201
    second = client.post("/api/service-assignments", json={"service_code": "parking", "room_id": room.id}, headers=auth_header(landlord))
    assert second.status_code == 201
    duplicate = client.post("/api/service-assignments", json={"service_code": "wifi", "room_id": room.id, "quantity": 1}, headers=auth_header(landlord))
    assert duplicate.status_code == 409
    duplicate_edit = client.put(
        f"/api/service-assignments/{second.json()['id']}",
        json={"service_code": "wifi"},
        headers=auth_header(landlord),
    )
    assert duplicate_edit.status_code == 409

    invalid = client.post("/api/service-assignments", json={"service_code": "wifi", "room_id": room.id, "quantity": 0}, headers=auth_header(landlord))
    assert invalid.status_code == 422

    missing = client.post("/api/service-assignments", json={"service_code": "cleaning", "room_id": room.id, "quantity": 1}, headers=auth_header(landlord))
    assert missing.status_code == 201
    assert missing.json()["unit_price"] is None
    assert missing.json()["billing_unit"] is None

    contract = make_contract(db_session, room.id, tenant.id, landlord.id, status="active")
    contract_add = client.post("/api/service-assignments", json={"service_code": "parking", "contract_id": contract.id, "quantity": 2, "price_override": 200000}, headers=auth_header(landlord))
    assert contract_add.status_code == 201, contract_add.text

    effective = client.get(f"/api/contracts/{contract.id}/services", headers=auth_header(landlord))
    assert effective.status_code == 200, effective.text
    payload = effective.json()
    assert any(item["service_code"] == "wifi" and item["source"] == "room" for item in payload)
    inherited_without_price = next(item for item in payload if item["service_code"] == "cleaning")
    assert inherited_without_price["source"] == "room"
    assert inherited_without_price["unit_price"] is None
    assert any(item["service_code"] == "parking" and item["source"] == "contract" and item["effective_price"] == 200000 for item in payload)
    inherited = next(item for item in payload if item["service_code"] == "wifi")
    assert inherited["assignment_id"] == first.json()["id"]
    assert inherited["room_id"] == room.id

    list_resp = client.get(f"/api/service-assignments?contract_id={contract.id}", headers=auth_header(landlord))
    assert list_resp.status_code == 200
    assert any(item["service_code"] == "parking" for item in list_resp.json())


def test_clear_service_price_prevents_delete_until_assignment_removed(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "landlord3@example.com", "0900000021")
    prop = make_property(db_session, landlord.id)
    room = make_room(db_session, prop.id, "P203")
    make_service_price(db_session, prop.id, "wifi", "room_month", 50000)
    create = client.post("/api/service-assignments", json={"service_code": "wifi", "room_id": room.id, "quantity": 1}, headers=auth_header(landlord))
    assert create.status_code == 201
    blocked = client.delete(f"/api/properties/{prop.id}/service-prices/wifi", headers=auth_header(landlord))
    assert blocked.status_code == 409

    delete_assignment = client.delete(f"/api/service-assignments/{create.json()['id']}", headers=auth_header(landlord))
    assert delete_assignment.status_code == 204
    allowed = client.delete(f"/api/properties/{prop.id}/service-prices/wifi", headers=auth_header(landlord))
    assert allowed.status_code == 204


def test_service_price_catalog_lists_six_services_and_validates_configuration(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "catalog@example.com", "0900000031")
    prop = make_property(db_session, landlord.id)
    headers = auth_header(landlord)

    response = client.get(f"/api/properties/{prop.id}/service-prices", headers=headers)
    assert response.status_code == 200
    services = response.json()
    assert {item["code"] for item in services} == {
        "electricity", "water", "wifi", "trash", "cleaning", "parking",
    }
    assert all(item["unit_price"] is None for item in services)

    invalid_unit = client.put(
        f"/api/properties/{prop.id}/service-prices/wifi",
        json={"billing_unit": "vehicle_month", "unit_price": 100000},
        headers=headers,
    )
    assert invalid_unit.status_code == 422

    negative_price = client.put(
        f"/api/properties/{prop.id}/service-prices/wifi",
        json={"billing_unit": "room_month", "unit_price": -1},
        headers=headers,
    )
    assert negative_price.status_code == 422

    configured = client.put(
        f"/api/properties/{prop.id}/service-prices/wifi",
        json={"billing_unit": "room_month", "unit_price": 100000},
        headers=headers,
    )
    assert configured.status_code == 200
    assert configured.json()["unit_price"] == 100000

    updated = client.put(
        f"/api/properties/{prop.id}/service-prices/wifi",
        json={"billing_unit": "room_month", "unit_price": 125000},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["unit_price"] == 125000


def test_assignment_quantity_and_clearing_override_and_ended_contract(client, db_session):
    landlord = make_user(db_session, "landlord", "Landlord", "quantity@example.com", "0900000041")
    tenant = make_tenant(db_session, landlord.id, "Tenant quantity")
    prop = make_property(db_session, landlord.id)
    room = make_room(db_session, prop.id, "P204")
    headers = auth_header(landlord)

    created = client.post(
        "/api/service-assignments",
        json={"service_code": "electricity", "room_id": room.id, "price_override": 2500},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assignment_id = created.json()["id"]
    assert created.json()["quantity"] == 1
    assert created.json()["unit_price"] is None

    updated = client.put(
        f"/api/service-assignments/{assignment_id}",
        json={"quantity": 3, "price_override": None},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["quantity"] == 3
    assert updated.json()["price_override"] is None
    assert updated.json()["effective_price"] is None

    changed_service = client.put(
        f"/api/service-assignments/{assignment_id}",
        json={"service_code": "water"},
        headers=headers,
    )
    assert changed_service.status_code == 200
    assert changed_service.json()["service_code"] == "water"

    contract = make_contract(db_session, room.id, tenant.id, landlord.id)
    make_service_price(db_session, prop.id, "wifi", "room_month", 50000)
    contract_assignment = client.post(
        "/api/service-assignments",
        json={"service_code": "wifi", "contract_id": contract.id},
        headers=headers,
    )
    assert contract_assignment.status_code == 201
    db_session.refresh(contract)
    contract.status = "active"
    contract.end_date = date.today() - timedelta(days=1)
    db_session.commit()

    expired_by_date = client.put(
        f"/api/service-assignments/{contract_assignment.json()['id']}",
        json={"quantity": 2},
        headers=headers,
    )
    assert expired_by_date.status_code == 409

    contract.status = "terminated"
    db_session.commit()

    rejected_update = client.put(
        f"/api/service-assignments/{contract_assignment.json()['id']}",
        json={"quantity": 2},
        headers=headers,
    )
    assert rejected_update.status_code == 409
    rejected_delete = client.delete(
        f"/api/service-assignments/{contract_assignment.json()['id']}",
        headers=headers,
    )
    assert rejected_delete.status_code == 409
