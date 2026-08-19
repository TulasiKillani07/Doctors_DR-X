"""
Auth schemas for DRX
"""

import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional


# ══════════════════════════════════════════════════════════════
# Password Validation (shared across all password fields)
# ══════════════════════════════════════════════════════════════

PASSWORD_REGEX = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?~`])[A-Za-z\d!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?~`]{8,64}$'
)

PASSWORD_ERROR = (
    "Password must be 8-64 characters and include at least one uppercase letter, "
    "one lowercase letter, one number, and one symbol. "
    "Only English letters, numbers, and standard symbols are allowed."
)


def validate_password_strength(password: Optional[str]) -> Optional[str]:
    """Validate password meets strength requirements. Returns password if valid."""
    if password is None:
        return None
    if not PASSWORD_REGEX.match(password):
        raise ValueError(PASSWORD_ERROR)
    return password


# ══════════════════════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class DoctorRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=30, description="Unique username (3-30 chars, alphanumeric + underscores)")
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8, max_length=64)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_]{3,30}$', v):
            raise ValueError("Username must be 3-30 characters, only letters, numbers, and underscores allowed")
        return v.lower()  # Store lowercase for case-insensitive uniqueness

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class DoctorLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email, Username, or Doctor GID (e.g. arjun@doctor.com, arjun_mehta, or PRXDOC482915)")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user: dict


class MessageResponse(BaseModel):
    message: str
    user_id: Optional[str] = None
    doctor_gid: Optional[str] = None
