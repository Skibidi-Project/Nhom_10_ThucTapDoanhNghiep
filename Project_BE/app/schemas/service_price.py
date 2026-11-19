from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ServiceCode(str, Enum):
    ELECTRICITY = "electricity"
    WATER = "water"
    WIFI = "wifi"
    TRASH = "trash"
    CLEANING = "cleaning"
    PARKING = "parking"


class BillingUnit(str, Enum):
    KWH = "kwh"
    CUBIC_METER = "m3"
    PERSON_MONTH = "person_month"
    ROOM_MONTH = "room_month"
    VEHICLE_MONTH = "vehicle_month"


class ServicePriceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_unit: BillingUnit
    unit_price: int = Field(strict=True, ge=0, le=2_147_483_647)


class ServicePriceResponse(BaseModel):
    code: ServiceCode
    name: str
    allowed_units: tuple[BillingUnit, ...]
    billing_unit: BillingUnit | None = None
    unit_price: int | None = None
