"""
Auth schemas for DRX
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from app.utils.validators import (
    validate_username as _v_username,
    validate_password as _v_password,
    validate_full_name as _v_fullname,
    validate_phone as _v_phone,
    validate_email_domain as _v_email_domain,
)


# ══════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email or Username")
    password: str


class AdminCreateRequest(BaseModel):
    name: str = Field(..., description="Full name (8-64 characters)")
    username: str = Field(..., description="Unique username (6-16 chars, letters/numbers/underscore)")
    email: EmailStr
    password: str = Field(..., description="8-24 chars, 1 upper, 1 lower, 1 number, 1 symbol")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _v_fullname(v)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        return _v_username(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _v_password(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _v_email_domain(v)


class DoctorRegisterRequest(BaseModel):
    name: str = Field(..., description="Full name (8-64 characters)")
    username: str = Field(..., description="Unique username (6-16 chars, letters/numbers/underscore)")
    email: EmailStr
    phone: str = Field(..., description="E.164 format, e.g. +919848012345")
    password: str = Field(..., description="8-24 chars, 1 upper, 1 lower, 1 number, 1 symbol")

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return _v_fullname(v)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        return _v_username(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return _v_phone(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        return _v_password(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return _v_email_domain(v)


class DoctorLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email, Username, or Doctor GID (e.g. arjun@doctor.com, arjun_mehta, or PRXDOC482915)")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: dict


class AdminMessageResponse(BaseModel):
    message: str
    user_id: Optional[str] = None


class DoctorMessageResponse(BaseModel):
    message: str
    user_id: Optional[str] = None
    doctor_gid: Optional[str] = None
