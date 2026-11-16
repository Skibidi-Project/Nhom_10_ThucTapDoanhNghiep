from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.service_price import BillingUnit, ServiceCode


class ServiceAssignmentWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: ServiceCode
    room_id: int | None = Field(default=None, gt=0)
    contract_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(default=1, strict=True, ge=1, le=2_147_483_647)
    price_override: int | None = Field(default=None, strict=True, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def require_exactly_one_target(self):
        if (self.room_id is None) == (self.contract_id is None):
            raise ValueError("Phải chọn đúng một trong room_id hoặc contract_id.")
        return self


class ServiceAssignmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: ServiceCode | None = None
    quantity: int | None = Field(default=None, strict=True, ge=1, le=2_147_483_647)
    price_override: int | None = Field(default=None, strict=True, ge=0, le=2_147_483_647)


class ServiceAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_code: ServiceCode
    service_name: str
    billing_unit: BillingUnit | None
    unit_price: int | None
    price_override: int | None = None
    effective_price: int | None
    quantity: int
    room_id: int | None = None
    contract_id: int | None = None
    assigned_by: int
    created_at: datetime


class EffectiveServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_code: ServiceCode
    service_name: str
    billing_unit: BillingUnit | None
    unit_price: int | None
    price_override: int | None = None
    effective_price: int | None
    quantity: int
    source: str
    assignment_id: int
    room_id: int | None = None
    contract_id: int | None = None
