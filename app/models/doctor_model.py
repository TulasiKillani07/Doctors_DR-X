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
    location_id: str = Field(..., description="Unique location ID (auto-generated)")
    location_priority: str = Field(..., description="PRIMARY / SECONDARY / OTHER")
    facility_type: str = Field(..., description="HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER")
    facility_type_other: Optional[str] = Field(None, description="Detail when facility_type=OTHER")
    location_name: str = Field(..., description="Facility / hospital name")
    latitude: Optional[str] = Field(None, description="Latitude (string)")
    longitude: Optional[str] = Field(None, description="Longitude (string)")
    address: Optional[str] = Field(None, description="Full address")
    area: Optional[str] = Field(None, description="Area / locality")
    city: str = Field(..., description="City")
    district: str = Field(..., description="District")
    state: str = Field(..., description="State")
    country: str = Field(..., description="Country")
    postcode: str = Field(..., description="Postal / PIN code")
    location_source: Optional[str] = Field(default="MANUAL", description="CURRENT_LOCATION / MAP_SEARCH / MANUAL")
    status: str = Field(default="ACTIVE", description="ACTIVE / INACTIVE")
    added_at: datetime = Field(default_factory=datetime.utcnow)


class DoctorInDB(BaseModel):
    """Write model for doctors collection — identity + profile + locations"""
    doctor_gid: str = Field(default_factory=generate_doctor_gid, description="Global platform ID (e.g. PRXDOC482915). Immutable.")
    username: str = Field(..., min_length=3, max_length=30, description="Unique username (lowercase, alphanumeric + underscores)")
    email: EmailStr = Field(..., description="Doctor email (unique, login identifier)")
    phone: str = Field(..., description="Phone number (unique)")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")

    # Professional info
    specialization: Optional[str] = Field(None, max_length=100)
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
    source: Optional[str] = Field(None, description="Registration source (e.g. VOICE from DOBO)")
    registered_via: Optional[str] = Field(None, description="Which service registered this doctor")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(None)

    class Config:
        extra = "forbid"
