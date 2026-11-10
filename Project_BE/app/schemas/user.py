import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, field_validator

from app.core.rbac import Role


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=255)
    phone: str = Field(pattern=r"^0[0-9]{9}$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if value.isspace():
            raise ValueError("Mật khẩu không được chỉ chứa khoảng trắng.")
        return value


class UserLogin(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value):
        value = value.strip()
        if "@" in value:
            return str(TypeAdapter(EmailStr).validate_python(value))
        if not re.fullmatch(r"0[0-9]{9}", value):
            raise ValueError("Identifier phải là email hoặc số điện thoại 10 chữ số bắt đầu bằng 0.")
        return value


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, pattern=r"^0[0-9]{9}$")

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class RoleAssign(BaseModel):
    role: Role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    phone: str
    role: str
    created_at: datetime


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
