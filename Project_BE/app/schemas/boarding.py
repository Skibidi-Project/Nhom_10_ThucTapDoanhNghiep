import calendar
from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

MAX_CONTRACT_YEARS = 10
MAX_START_DATE_PAST_YEARS = 1
MAX_DEPOSIT_MONTHS = 3
ALLOWED_PAYMENT_CYCLES = {1, 2, 3, 6, 12}


class PropertyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    electricity_unit_price: int = Field(default=0, ge=0)
    water_unit_price: int = Field(default=0, ge=0)
    service_unit_price: int = Field(default=0, ge=0)

    @field_validator("name", "address", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class PropertyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    electricity_unit_price: int | None = Field(default=None, ge=0)
    water_unit_price: int | None = Field(default=None, ge=0)
    service_unit_price: int | None = Field(default=None, ge=0)

    @field_validator("name", "address", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    name: str
    address: str
    electricity_unit_price: int
    water_unit_price: int
    service_unit_price: int


class ManagerAssign(BaseModel):
    user_id: int = Field(gt=0)


class ManagerAssignmentResponse(BaseModel):
    property_id: int
    user_id: int


class RoomCreate(BaseModel):
    room_number: str = Field(min_length=1, max_length=20)
    area_sqm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    base_rent: int = Field(ge=0)

    @field_validator("room_number", mode="before")
    @classmethod
    def strip_number(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoomUpdate(BaseModel):
    room_number: str | None = Field(default=None, min_length=1, max_length=20)
    area_sqm: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    base_rent: int | None = Field(default=None, ge=0)
    status: str | None = None

    @field_validator("room_number", mode="before")
    @classmethod
    def strip_number(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is not None and value not in {"available", "reserved", "occupied", "maintenance"}:
            raise ValueError("Trạng thái phòng không hợp lệ.")
        return value


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    room_number: str
    area_sqm: Decimal | None
    base_rent: int
    status: str


class RoomListItem(RoomResponse):
    property_name: str


class RoomListResponse(BaseModel):
    items: list[RoomListItem]
    total: int
    page: int
    page_size: int


class RoomActiveContractResponse(BaseModel):
    id: int
    tenant: str
    start_date: date
    end_date: date
    monthly_rent: int


class RoomDetailResponse(RoomResponse):
    property_name: str
    active_contract: RoomActiveContractResponse | None


class TenantCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=r"^0[0-9]{9}$")
    id_number: str = Field(pattern=r"^[0-9]{9,12}$")
    email: EmailStr | None = None
    user_id: int | None = Field(default=None, gt=0)
    property_id: int | None = Field(default=None, gt=0)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class TenantUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, pattern=r"^0[0-9]{9}$")
    email: EmailStr | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    landlord_id: int
    user_id: int | None
    full_name: str
    phone: str
    id_number: str
    email: EmailStr | None


class ContractCreate(BaseModel):
    room_id: int = Field(gt=0)
    tenant_id: int = Field(gt=0)
    start_date: date
    end_date: date
    deposit: int = 0
    monthly_rent: int
    payment_cycle_months: int = Field(default=1)

    @field_validator("deposit")
    @classmethod
    def validate_deposit(cls, value):
        if value < 0:
            raise ValueError("Tiền cọc phải là số nguyên không âm.")
        return value

    @field_validator("monthly_rent")
    @classmethod
    def validate_monthly_rent(cls, value):
        if value <= 0:
            raise ValueError("Tiền thuê hàng tháng phải lớn hơn 0.")
        return value

    @field_validator("payment_cycle_months")
    @classmethod
    def validate_payment_cycle(cls, value):
        if value not in ALLOWED_PAYMENT_CYCLES:
            raise ValueError("Kỳ thanh toán chỉ được là 1, 2, 3, 6 hoặc 12 tháng.")
        return value

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu.")
        today = date.today()
        earliest_start = date(
            today.year - MAX_START_DATE_PAST_YEARS,
            today.month,
            min(today.day, calendar.monthrange(today.year - MAX_START_DATE_PAST_YEARS, today.month)[1]),
        )
        if self.start_date < earliest_start:
            raise ValueError("Ngày bắt đầu không được trước hôm nay quá 1 năm.")
        end_year = self.start_date.year + MAX_CONTRACT_YEARS
        latest_end = date(
            end_year,
            self.start_date.month,
            min(self.start_date.day, calendar.monthrange(end_year, self.start_date.month)[1]),
        )
        if self.end_date > latest_end:
            raise ValueError("Thời hạn hợp đồng không được vượt quá 10 năm.")
        if self.deposit > MAX_DEPOSIT_MONTHS * self.monthly_rent:
            raise ValueError("Tiền cọc không được vượt quá 3 tháng tiền thuê.")
        return self


class ContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    tenant_id: int
    created_by: int
    start_date: date
    end_date: date
    deposit: int
    monthly_rent: int
    payment_cycle_months: int
    status: str
    room_number: str
    property_id: int
    property_name: str
    tenant_name: str


class UtilityType(str, Enum):
    ELECTRICITY = "electricity"
    WATER = "water"
    SERVICE = "service"


class ReadingCreate(BaseModel):
    utility_type: UtilityType
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    previous_reading: int = Field(ge=0)
    current_reading: int = Field(ge=0)

    @model_validator(mode="after")
    def check_index(self):
        if self.current_reading < self.previous_reading:
            raise ValueError("Chỉ số hiện tại phải lớn hơn hoặc bằng chỉ số kỳ trước.")
        return self


class ReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    utility_type: str
    period: str
    previous_reading: int
    current_reading: int
    recorded_by: int


class InvoiceCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    period: str
    rent_amount: int
    utility_amount: int
    total_amount: int
    status: str


class PaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    method: str = Field(default="cash", min_length=1, max_length=30)


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_id: int
    amount: int
    method: str
    recorded_by: int
