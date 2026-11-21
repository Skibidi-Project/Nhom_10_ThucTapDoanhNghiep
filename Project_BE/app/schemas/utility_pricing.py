from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class PriceCreate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    property_id: int = Field(gt=0)
    room_id: int | None = Field(default=None,gt=0)
    contract_id: int | None = Field(default=None,gt=0)
    utility: Literal['electricity','water']
    unit_price: int = Field(strict=True,ge=0,le=2147483647)
    valid_from: date
    valid_to: date
    evidence: str = Field(min_length=3,max_length=500)
    @model_validator(mode='after')
    def validate_period(self):
        if self.valid_to < self.valid_from: raise ValueError('invalid date range')
        if self.room_id is not None and self.contract_id is not None: raise ValueError('choose one scope')
        return self
