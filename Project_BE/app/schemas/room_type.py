from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RoomTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    # Giá VNĐ nguyên, tương thích base_rent; giới hạn theo MySQL INT có dấu.
    listed_price: int = Field(strict=True, ge=0, le=2147483647)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoomTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default=None, min_length=1, max_length=150)
    listed_price: int = Field(default=None, strict=True, ge=0, le=2147483647)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set:
            raise ValueError("Cần cung cấp tên hoặc đơn giá niêm yết.")
        return self


class RoomTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_id: int
    name: str
    listed_price: int
