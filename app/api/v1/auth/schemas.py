"""
Auth schemas for DRX
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8, max_length=72, description="Optional — defaults to Welcome@123")


class DoctorRegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    password: Optional[str] = Field(None, min_length=8, max_length=72, description="Optional — defaults to Welcome@123")


class DoctorLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email or Doctor GID (e.g. arjun@doctor.com or PRXDOC482915)")
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
