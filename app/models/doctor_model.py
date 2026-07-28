"""
Doctor model — end users who register on the platform
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
import random


def generate_doctor_gid() -> str:
    """Generate unique doctor GID: PRXDOC + 6 random digits"""
    return f"PRXDOC{random.randint(100000, 999999)}"


class DoctorLocation(BaseModel):
    """A doctor's practice location"""
    id: str = Field(..., description="Unique location ID")
    type: str = Field(default="hospital", description="hospital, solo_clinic, or polyclinic")
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    address: str = Field(..., max_length=500, description="Full address")
    country: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    district: str = Field(..., max_length=100)
    city: str = Field(..., max_length=100)
    area: str = Field(..., max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    is_active: bool = Field(default=True)
    geofence_radius: int = Field(default=100, ge=10, le=1000)
    added_by: str = Field(..., description="User ID who added this location")
    added_at: datetime = Field(default_factory=datetime.utcnow)


class DoctorInDB(BaseModel):
    """Write model for doctors collection — identity + profile + locations"""
    doctor_gid: str = Field(default_factory=generate_doctor_gid, description="Global platform ID (e.g. PRXDOC482915). Immutable.")
    email: EmailStr = Field(..., description="Doctor email (unique, login identifier)")
    phone: str = Field(..., description="Phone number (unique)")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")

    # Professional info
    specialization: Optional[str] = Field(None, max_length=100)
    hospital: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    experience_years: Optional[float] = Field(None, ge=0, le=70)
    qualification: Optional[str] = Field(None, max_length=200)

    # Personal info
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200, description="City/area text")
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)

    # Locations (practice locations with coordinates)
    locations: List[DoctorLocation] = Field(default_factory=list)

    # Status
    is_active: bool = Field(default=True)
    is_email_verified: bool = Field(default=False)
    is_phone_verified: bool = Field(default=False)
    registered_via: Optional[str] = Field(None, description="Which service registered this doctor (e.g. client_id of MRX)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(None)

    class Config:
        extra = "forbid"
