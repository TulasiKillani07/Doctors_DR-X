"""
Doctor management schemas — DRX Doctor Platform
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from app.utils.validators import (
    validate_username as _v_username,
    validate_password as _v_password,
    validate_full_name as _v_fullname,
    validate_phone as _v_phone,
    validate_email_domain as _v_email_domain,
)
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
    """Doctor practice location from map/GPS/manual entry"""
    location_id: Optional[str] = Field(None, description="Unique location ID (auto-generated server-side)")
    location_priority: str = Field(..., description="PRIMARY / SECONDARY / OTHER")
    facility_type: str = Field(..., description="HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER")
    facility_type_other: Optional[str] = Field(None, description="Required only when facility_type=OTHER")
    location_name: str = Field(..., description="Facility / hospital name")
    latitude: Optional[str] = Field(None, description="Latitude (kept as string)")
    longitude: Optional[str] = Field(None, description="Longitude (kept as string)")
    address: Optional[str] = Field(None, description="Full address")
    area: Optional[str] = Field(None, description="Area / locality")
    city: str = Field(..., description="City")
    district: str = Field(..., description="District")
    state: str = Field(..., description="State")
    country: str = Field(..., description="Country")
    postcode: str = Field(..., description="Postal / PIN code")
    location_source: Optional[str] = Field("MANUAL", description="CURRENT_LOCATION / MAP_SEARCH / MANUAL")
    status: Optional[str] = Field("ACTIVE", description="ACTIVE / INACTIVE")

    @field_validator("location_priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        allowed = {"PRIMARY", "SECONDARY", "OTHER"}
        if v.upper() not in allowed:
            raise ValueError(f"location_priority must be one of {allowed}")
        return v.upper()

    @field_validator("facility_type")
    @classmethod
    def validate_facility_type(cls, v: str) -> str:
        allowed = {"HOSPITAL", "CLINIC", "POLYCLINIC", "MEDICAL_CENTER", "INSTITUTION_OR_MEDICAL_COLLEGE", "OTHER"}
        if v.upper() not in allowed:
            raise ValueError(f"facility_type must be one of {allowed}")
        return v.upper()

    @field_validator("location_source")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"CURRENT_LOCATION", "MAP_SEARCH", "MANUAL"}
        if v.upper() not in allowed:
            raise ValueError(f"location_source must be one of {allowed}")
        return v.upper()

    @model_validator(mode="after")
    def check_facility_type_other(self):
        if self.facility_type == "OTHER" and not self.facility_type_other:
            raise ValueError("facility_type_other is required when facility_type is OTHER")
        return self


class AddDoctorRequest(BaseModel):
    """Admin manually adds a single doctor"""
    name: str = Field(..., description="Full name (8-64 characters)")
    username: str = Field(..., description="Unique username (6-16 chars, letters/numbers/underscore)")
    email: str = Field(..., description="Doctor email")
    phone: str = Field(..., description="E.164 format, e.g. +919848012345")
    password: str = Field(..., description="8-24 chars, 1 upper, 1 lower, 1 number, 1 symbol")
    specialization: Optional[str] = Field(None, description="Must be from predefined list")
    qualification: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=50)
    location: Optional[LocationInput] = Field(None, description="Doctor's practice location")

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
                "qualification": "MBBS, MD Cardiology",
                "location": {
                    "location_priority": "PRIMARY",
                    "facility_type": "HOSPITAL",
                    "location_name": "Apollo Hospital",
                    "latitude": "17.4401",
                    "longitude": "78.3489",
                    "address": "Road 45, Jubilee Hills",
                    "area": "Jubilee Hills",
                    "city": "Hyderabad",
                    "district": "Hyderabad",
                    "state": "Telangana",
                    "country": "India",
                    "postcode": "500033",
                    "location_source": "MAP_SEARCH",
                    "status": "ACTIVE"
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DoctorUpdateByAdminRequest(BaseModel):
    """Fields an admin can update on a doctor"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    specialization: Optional[str] = Field(None, description="Must be one of the predefined specializations")
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

FACILITY_TYPES = {"HOSPITAL", "CLINIC", "POLYCLINIC", "MEDICAL_CENTER", "INSTITUTION_OR_MEDICAL_COLLEGE", "OTHER"}
LOCATION_PRIORITIES = {"PRIMARY", "SECONDARY", "OTHER"}
LOCATION_SOURCES = {"CURRENT_LOCATION", "MAP_SEARCH", "MANUAL"}


class AddLocationRequest(BaseModel):
    """Add a practice location to a doctor's own profile"""
    location_priority: str = Field(..., description="PRIMARY / SECONDARY / OTHER")
    facility_type: str = Field(..., description="HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER")
    facility_type_other: Optional[str] = Field(None, description="Required only when facility_type=OTHER")
    location_name: str = Field(..., min_length=1, max_length=200)
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)
    area: Optional[str] = Field(None, max_length=200)
    city: str = Field(..., max_length=100)
    district: str = Field(..., max_length=100)
    state: str = Field(..., max_length=100)
    country: str = Field(..., max_length=100)
    postcode: str = Field(...)
    location_source: Optional[str] = Field("MANUAL", description="CURRENT_LOCATION / MAP_SEARCH / MANUAL")
    status: Optional[str] = Field("ACTIVE")

    @field_validator("facility_type")
    @classmethod
    def _vt(cls, v: str) -> str:
        if v.upper() not in FACILITY_TYPES:
            raise ValueError(f"facility_type must be one of {FACILITY_TYPES}")
        return v.upper()

    @field_validator("location_priority")
    @classmethod
    def _vp(cls, v: str) -> str:
        if v.upper() not in LOCATION_PRIORITIES:
            raise ValueError(f"location_priority must be one of {LOCATION_PRIORITIES}")
        return v.upper()

    @model_validator(mode="after")
    def check_facility_type_other(self):
        if self.facility_type == "OTHER" and not self.facility_type_other:
            raise ValueError("facility_type_other is required when facility_type is OTHER")
        return self


class UpdateLocationRequest(BaseModel):
    """Update an existing location (all optional)"""
    location_priority: Optional[str] = None
    facility_type: Optional[str] = None
    facility_type_other: Optional[str] = None
    location_name: Optional[str] = Field(None, max_length=200)
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)
    area: Optional[str] = Field(None, max_length=200)
    city: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postcode: Optional[str] = None
    location_source: Optional[str] = None
    status: Optional[str] = None


class SetLocationPriorityRequest(BaseModel):
    """Change a location's priority"""
    priority: str = Field(..., description="PRIMARY / SECONDARY / OTHER")


class LocationResponse(BaseModel):
    location_id: str
    location_priority: str
    facility_type: str
    facility_type_other: Optional[str] = None
    location_name: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    address: Optional[str] = None
    area: Optional[str] = None
    city: str
    district: Optional[str] = None
    state: str
    country: str
    postcode: Optional[str] = None
    location_source: Optional[str] = None
    status: str


class LocationListResponse(BaseModel):
    total: int
    locations: List[LocationResponse]


class MessageResponse(BaseModel):
    message: str
