from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class ExpenseCategory(str, Enum):
    REPAIR = "repair"
    SUPPLIES = "supplies"
    OPERATIONS = "operations"
    CLEANING = "cleaning"
    OTHER = "other"


CATEGORY_LABELS = {
    "repair": "Sửa chữa",
    "supplies": "Vật tư",
    "operations": "Vận hành",
    "cleaning": "Vệ sinh",
    "other": "Khác",
}


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    property_id: int = Field(gt=0)
    room_id: int | None = Field(default=None, gt=0)
    category: ExpenseCategory
    description: str = Field(min_length=1, max_length=255)
    vendor: str | None = Field(default=None, max_length=120)
    amount: StrictInt = Field(gt=0, le=2_000_000_000)
    expense_date: date

    @field_validator("description", "vendor", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: int | None = Field(default=None, gt=0)
    category: ExpenseCategory | None = None
    description: str | None = Field(default=None, min_length=1, max_length=255)
    vendor: str | None = Field(default=None, max_length=120)
    amount: StrictInt | None = Field(default=None, gt=0, le=2_000_000_000)
    expense_date: date | None = None

    @field_validator("description", "vendor", mode="before")
    @classmethod
    def strip_optional_text(cls, value):
        if value is None:
            return None
        return value.strip() if isinstance(value, str) else value

    @field_validator("description")
    @classmethod
    def description_required(cls, value):
        if value is None:
            raise ValueError("Nội dung chi phí không được để trống.")
        return value


class ExpenseItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    property_name: str
    room_id: int | None
    room_number: str | None
    category: str
    category_label: str
    description: str
    vendor: str | None
    amount: int
    expense_date: date
    created_by: int
    created_by_name: str
    created_at: datetime


class ExpenseListResponse(BaseModel):
    items: list[ExpenseItem]
    total: int
    page: int
    page_size: int
    total_amount: int


class ExpenseCategorySummary(BaseModel):
    category: str
    category_label: str
    total: int
    count: int


class ExpenseSummaryResponse(BaseModel):
    total_amount: int
    count: int
    by_category: list[ExpenseCategorySummary]
