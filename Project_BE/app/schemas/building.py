from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    floor_count: int = Field(ge=1, le=30)
    floor_names: list[str] | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("floor_names", mode="before")
    @classmethod
    def strip_floor_names(cls, value):
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value

    @model_validator(mode="after")
    def validate_floors(self):
        check_floor_names(self.floor_names)
        if self.floor_names is not None and len(self.floor_names) != self.floor_count:
            raise ValueError("Số tên tầng phải bằng số lượng tầng.")
        return self


class BuildingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    floor_count: int | None = Field(default=None, ge=1, le=30)
    floor_names: list[str] | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("floor_names", mode="before")
    @classmethod
    def strip_floor_names(cls, value):
        if isinstance(value, list):
            return [item.strip() if isinstance(item, str) else item for item in value]
        return value

    @model_validator(mode="after")
    def validate_floors(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} không được là null.")
        check_floor_names(self.floor_names)
        if self.floor_count is not None and self.floor_names is not None:
            if len(self.floor_names) != self.floor_count:
                raise ValueError("Số tên tầng phải bằng số lượng tầng.")
        return self


class FloorRename(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class FloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    building_id: int
    number: int
    name: str


class BuildingResponse(BaseModel):
    id: int
    property_id: int
    name: str
    floor_count: int
    floors: list[FloorResponse]


def check_floor_names(names: list[str] | None) -> None:
    if names is None:
        return
    if any(not isinstance(name, str) or not name or len(name) > 80 for name in names):
        raise ValueError("Mỗi tên tầng phải có từ 1 đến 80 ký tự.")
    if len({name.casefold() for name in names}) != len(names):
        raise ValueError("Tên tầng không được trùng nhau trong cùng tòa nhà.")
