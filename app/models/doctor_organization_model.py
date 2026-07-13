"""
Doctor-Organization relationship model
Represents the complete lifecycle: PENDING → ACTIVE / REJECTED / REMOVED
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum
from bson import ObjectId


class RelationshipStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    REMOVED = "REMOVED"


class DoctorOrganizationInDB(BaseModel):
    """Write model for doctor_organizations collection"""
    doctor_id: str = Field(..., description="Doctor MongoDB _id")
    organization_id: str = Field(..., description="Organization MongoDB _id")
    status: RelationshipStatus = Field(default=RelationshipStatus.PENDING, description="Relationship status")
    requested_by: str = Field(..., description="Admin user ID who initiated the request")
    requested_at: datetime = Field(default_factory=datetime.utcnow, description="When the request was created")
    responded_at: Optional[datetime] = Field(None, description="When doctor responded (accept/reject)")
    joined_at: Optional[datetime] = Field(None, description="When relationship became ACTIVE")
    removed_at: Optional[datetime] = Field(None, description="When relationship was REMOVED")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('doctor_id', 'organization_id', 'requested_by')
    @classmethod
    def validate_object_id(cls, v: str) -> str:
        try:
            ObjectId(v)
            return v
        except Exception:
            raise ValueError(f'Invalid ObjectId format: {v}')

    class Config:
        extra = "forbid"
