from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TenantMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: int = Field(gt=0, strict=True)


class ClassifiedTenant(BaseModel):
    tenant_id: int
    full_name: str
    classification: Literal["representative", "member"]


class TenantGroupResponse(BaseModel):
    contract_id: int
    room_id: int
    representative: ClassifiedTenant
    members: list[ClassifiedTenant]
