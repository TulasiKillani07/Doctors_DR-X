"""
Profile schemas for DRX Doctor Platform
"""

from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.api.v1.doctors.schemas import SPECIALIZATIONS


class DoctorProfileResponse(BaseModel):
    """Complete doctor profile (returned from GET /profile/me)"""
    user_id: str
    doctor_gid: str
    email: str
    phone: str
    name: str
    role: str = "DOCTOR"

    # Professional info
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    experience_years: Optional[float] = None
    qualification: Optional[str] = None

    # Personal info
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # Status
    is_active: bool = True
    is_email_verified: bool = False
    is_phone_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DoctorProfileUpdateRequest(BaseModel):
    """Fields a doctor can update on their own profile"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)

    # Professional
    specialization: Optional[str] = Field(None, description="Must be one of the predefined specializations")
    hospital: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    experience_years: Optional[float] = Field(None, ge=0, le=70)
    qualification: Optional[str] = Field(None, max_length=200)

    # Personal
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)

    @field_validator("specialization")
    @classmethod
    def validate_specialization(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SPECIALIZATIONS:
            raise ValueError("Invalid specialization. Use GET /doctors/specializations for valid options.")
        return v

    class Config:
        extra = "forbid"
