"""
Doctor management schemas — DRX Doctor Platform
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ── Specialization options (dropdown) ──
SPECIALIZATIONS = [
    "General Physician", "General Medicine", "Family Medicine", "Emergency Medicine",
    "Cardiology", "Neurology", "Nephrology", "Gastroenterology", "Endocrinology",
    "Pulmonology (Respiratory Medicine)", "Rheumatology", "Infectious Diseases",
    "Clinical Immunology", "Geriatric Medicine", "Critical Care Medicine",
    "Pediatrics", "Neonatology", "Pediatric Cardiology", "Pediatric Neurology",
    "Pediatric Nephrology", "Pediatric Gastroenterology", "Pediatric Endocrinology",
    "General Surgery", "Orthopedic Surgery", "Neurosurgery", "Plastic Surgery",
    "Cardiothoracic Surgery", "Vascular Surgery", "Urology", "Pediatric Surgery",
    "Surgical Gastroenterology", "Obstetrics & Gynecology", "Reproductive Medicine",
    "Medical Oncology", "Surgical Oncology", "Radiation Oncology", "Hematology",
    "Hemato-Oncology", "Dermatology", "Venereology", "Ophthalmology",
    "ENT (Otorhinolaryngology)", "Psychiatry", "Radiology", "Nuclear Medicine",
    "Pathology", "Microbiology", "Transfusion Medicine", "Anesthesiology",
    "Pain Medicine", "Palliative Medicine", "Physical Medicine & Rehabilitation",
    "Sports Medicine", "Dentistry", "Oral & Maxillofacial Surgery",
    "Community Medicine", "Preventive Medicine",
]


# ══════════════════════════════════════════════════════════════
# Bulk Upload
# ══════════════════════════════════════════════════════════════

class BulkUploadErrorDetail(BaseModel):
    row: int
    name: Optional[str] = None
    email: Optional[str] = None
    error: str


class BulkUploadResponse(BaseModel):
    total_rows: int
    successful: int
    failed: int
    errors: List[BulkUploadErrorDetail] = []
    message: str


# ══════════════════════════════════════════════════════════════
# Add Single Doctor
# ══════════════════════════════════════════════════════════════

class LocationInput(BaseModel):
    """Location data from map/GPS"""
    latitude: str = Field(..., description="Latitude from map/GPS")
    longitude: str = Field(..., description="Longitude from map/GPS")
    address: str = Field(..., description="Full address from geocode")
    city: str = Field(..., description="City from geocode")
    state: str = Field(..., description="State from geocode")
    country: str = Field(default="India", description="Country from geocode")


class AddDoctorRequest(BaseModel):
    """Admin manually adds a single doctor"""
    name: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=3, max_length=30, description="Unique username (3-30 chars, lowercase + numbers + underscore)")
    email: str = Field(..., description="Doctor email")
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=8, max_length=64, description="8-64 chars, 1 upper, 1 lower, 1 number, 1 symbol")
    specialization: Optional[str] = Field(None, description="Must be from predefined list")
    hospital: Optional[str] = Field(None, max_length=200)
    qualification: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    location: Optional[LocationInput] = Field(None, description="Doctor's practice location")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-z0-9_]{3,30}$', v):
            raise ValueError("Username must be 3-30 characters, only lowercase letters, numbers, and underscores")
        return v.lower()

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
        json_schema_extra = {
            "example": {
                "name": "Dr. Arjun Mehta",
                "username": "arjun_mehta",
                "email": "arjun@hospital.com",
                "phone": "9876543210",
                "password": "Doctor@123",
                "specialization": "Cardiology",
                "hospital": "Apollo Hospital",
                "qualification": "MBBS, MD Cardiology",
                "location": {
                    "latitude": "17.4401",
                    "longitude": "78.3489",
                    "address": "Apollo Hospital, Jubilee Hills",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "country": "India"
                }
            }
        }


class AddDoctorResponse(BaseModel):
    message: str
    doctor_id: str
    doctor_gid: str


# ══════════════════════════════════════════════════════════════
# Doctor CRUD (Admin)
# ══════════════════════════════════════════════════════════════

class DoctorDetailResponse(BaseModel):
    """Full doctor detail for admin view"""
    id: str
    doctor_gid: str
    email: str
    phone: str
    name: str
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    license_number: Optional[str] = None
    experience_years: Optional[float] = None
    qualification: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    locations: List[dict] = []
    is_active: bool = True
    is_email_verified: bool = False
    is_phone_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DoctorUpdateByAdminRequest(BaseModel):
    """Fields an admin can update on a doctor"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    specialization: Optional[str] = Field(None, description="Must be one of the predefined specializations")
    hospital: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    experience_years: Optional[float] = Field(None, ge=0, le=70)
    qualification: Optional[str] = Field(None, max_length=200)
    bio: Optional[str] = Field(None, max_length=500)
    avatar_url: Optional[str] = Field(None, max_length=500)
    location: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

    @field_validator("specialization")
    @classmethod
    def validate_specialization(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SPECIALIZATIONS:
            raise ValueError("Invalid specialization. Choose from the predefined list.")
        return v

    class Config:
        extra = "forbid"


class DoctorListItem(BaseModel):
    """Doctor in a list view"""
    id: str
    doctor_gid: str
    email: str
    phone: str
    name: str
    specialization: Optional[str] = None
    hospital: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None


class DoctorListResponse(BaseModel):
    total: int
    doctors: List[DoctorListItem]


# ══════════════════════════════════════════════════════════════
# Location Management
# ══════════════════════════════════════════════════════════════

class AddLocationRequest(BaseModel):
    """Add a practice location to a doctor"""
    name: str = Field(..., min_length=1, max_length=200)
    address: str = Field(..., max_length=500)
    country: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    district: str = Field(..., max_length=100)
    city: str = Field(..., max_length=100)
    area: str = Field(..., max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    type: str = Field(default="hospital", description="hospital, solo_clinic, or polyclinic")
    geofence_radius: int = Field(default=100, ge=10, le=1000)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"hospital", "solo_clinic", "polyclinic"}
        if v not in allowed:
            raise ValueError(f"type must be one of: {', '.join(sorted(allowed))}")
        return v


class UpdateLocationRequest(BaseModel):
    """Update an existing location"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    country: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    area: Optional[str] = Field(None, max_length=200)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    type: Optional[str] = None
    geofence_radius: Optional[int] = Field(None, ge=10, le=1000)
    is_active: Optional[bool] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"hospital", "solo_clinic", "polyclinic"}
        if v not in allowed:
            raise ValueError(f"type must be one of: {', '.join(sorted(allowed))}")
        return v


class LocationResponse(BaseModel):
    id: str
    type: str
    name: str
    address: str
    country: str
    state: str
    district: str
    city: str
    area: str
    latitude: float
    longitude: float
    is_active: bool
    geofence_radius: int
    is_primary: bool = False
    added_by: str
    added_at: datetime


class LocationListResponse(BaseModel):
    total: int
    locations: List[LocationResponse]


class MessageResponse(BaseModel):
    message: str
