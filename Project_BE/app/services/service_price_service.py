from fastapi import HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.boarding import Contract, PropertyServicePrice, Room
from app.models.service_assignment import ServiceAssignment
from app.schemas.service_price import BillingUnit, ServiceCode, ServicePriceResponse, ServicePriceWrite
from app.services.db_util import save


CATALOG = {
    ServiceCode.ELECTRICITY: ("Điện", (BillingUnit.KWH,)),
    ServiceCode.WATER: ("Nước", (BillingUnit.CUBIC_METER, BillingUnit.PERSON_MONTH)),
    ServiceCode.WIFI: ("Wifi", (BillingUnit.ROOM_MONTH,)),
    ServiceCode.TRASH: ("Rác", (BillingUnit.ROOM_MONTH,)),
    ServiceCode.CLEANING: ("Vệ sinh chung", (BillingUnit.ROOM_MONTH,)),
    ServiceCode.PARKING: ("Gửi xe", (BillingUnit.VEHICLE_MONTH,)),
}


def list_service_prices(db: Session, property_id: int) -> list[ServicePriceResponse]:
    rows = db.scalars(select(PropertyServicePrice).where(PropertyServicePrice.property_id == property_id))
    configured = {row.service_code: row for row in rows}
    return [
        ServicePriceResponse(
            code=code,
            name=name,
            allowed_units=units,
            billing_unit=entry.billing_unit if (entry := configured.get(code.value)) else None,
            unit_price=entry.unit_price if entry else None,
        )
        for code, (name, units) in CATALOG.items()
    ]


def set_service_price(
    db: Session, property_id: int, code: ServiceCode, data: ServicePriceWrite
) -> ServicePriceResponse:
    name, allowed_units = CATALOG[code]
    if data.billing_unit not in allowed_units:
        raise HTTPException(status_code=422, detail="Đơn vị tính không phù hợp với dịch vụ.")

    from app.services.trial_input_guard import touch_property_inputs
    touch_property_inputs(db, property_id)

    prices = PropertyServicePrice.__table__
    changes = {"billing_unit": data.billing_unit.value, "unit_price": data.unit_price}
    values = {"property_id": property_id, "service_code": code.value, **changes}
    if db.get_bind().dialect.name == "sqlite":
        stmt = sqlite_insert(prices).values(**values).on_conflict_do_update(
            index_elements=[prices.c.property_id, prices.c.service_code], set_=changes
        )
    else:
        stmt = mysql_insert(prices).values(**values).on_duplicate_key_update(**changes)
    db.execute(stmt)
    save(db)
    return ServicePriceResponse(code=code, name=name, allowed_units=allowed_units, **changes)


def clear_service_price(db: Session, property_id: int, code: ServiceCode) -> None:
    from app.services.trial_input_guard import touch_property_inputs
    touch_property_inputs(db, property_id)
    room_assignment = db.scalar(
        select(ServiceAssignment.id)
        .join(Room, Room.id == ServiceAssignment.room_id)
        .where(
            Room.property_id == property_id,
            ServiceAssignment.service_code == code.value,
        )
    )
    contract_assignment = db.scalar(
        select(ServiceAssignment.id)
        .join(Contract, Contract.id == ServiceAssignment.contract_id)
        .join(Room, Room.id == Contract.room_id)
        .where(
            Room.property_id == property_id,
            ServiceAssignment.service_code == code.value,
        )
    )
    if room_assignment is not None or contract_assignment is not None:
        raise HTTPException(status_code=409, detail="Không thể xóa đơn giá của dịch vụ đang được gán.")
    db.execute(delete(PropertyServicePrice).where(
        PropertyServicePrice.property_id == property_id,
        PropertyServicePrice.service_code == code.value,
    ))
    save(db)
