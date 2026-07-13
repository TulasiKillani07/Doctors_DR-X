"""
Doctor model — end users who register on the platform
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import random


def generate_doctor_gid() -> str:
    """Generate unique doctor GID: PRXDOC + 6 random digits"""
    return f"PRXDOC{random.randint(100000, 999999)}"


class DoctorInDB(BaseModel):
    """Write model for doctors collection — authentication + identity"""
    doctor_gid: str = Field(default_factory=generate_doctor_gid, description="Global platform ID (e.g. PRXDOC482915). Immutable.")
    email: EmailStr = Field(..., description="Doctor email (unique, login identifier)")
    phone: str = Field(..., description="Phone number (unique)")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    is_active: bool = Field(default=True, description="Account active")
    is_email_verified: bool = Field(default=False, description="Email verified")
    is_phone_verified: bool = Field(default=False, description="Phone verified")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(None)

    class Config:
        extra = "forbid"
