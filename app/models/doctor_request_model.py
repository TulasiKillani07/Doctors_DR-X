"""
Doctor Request model — MRX admin requests a doctor to join their organization.
Collection: doctor_requests

Flow:
  MRX Admin → request → PENDING_DOCTOR
  Doctor accepts → PENDING_ADMIN
  Doctor rejects → REJECTED_BY_DOCTOR
  DRX Admin approves → APPROVED (auto-links doctor to org + syncs to MRX)
  DRX Admin rejects → REJECTED_BY_ADMIN
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


class RequestStatus(str, Enum):
    PENDING_DOCTOR = "PENDING_DOCTOR"
    PENDING_ADMIN = "PENDING_ADMIN"
    APPROVED = "APPROVED"
    REJECTED_BY_DOCTOR = "REJECTED_BY_DOCTOR"
    REJECTED_BY_ADMIN = "REJECTED_BY_ADMIN"


class DoctorRequestInDB(BaseModel):
    """Write model for doctor_requests collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_gid: str = Field(..., description="Doctor's global ID (PRXDOC...)")
    doctor_id: str = Field(..., description="Doctor's MongoDB _id")
    organization_id: str = Field(..., description="Organization MongoDB _id")
    organization_name: str = Field(..., description="Organization name (denormalized for display)")
    requested_by: str = Field(..., description="MRX admin username (from Proxzar sub)")
    status: str = Field(default=RequestStatus.PENDING_DOCTOR)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    doctor_responded_at: Optional[datetime] = Field(None)
    admin_responded_at: Optional[datetime] = Field(None)
    admin_responded_by: Optional[str] = Field(None, description="DRX admin username who approved/rejected")
