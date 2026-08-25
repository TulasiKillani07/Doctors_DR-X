"""
Doctor Request model — MRX admin requests a doctor to join their organization.
Collection: doctor_requests

Flow:
  MRX Admin → request → PENDING
  Doctor accepts → PENDING (waiting for admin)
  Doctor rejects → REJECTED (done, never reaches admin)
  DRX Admin approves → APPROVED (auto-links doctor to org + syncs to MRX)
  DRX Admin rejects → REJECTED (done)
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from enum import Enum


class RequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DoctorRequestInDB(BaseModel):
    """Write model for doctor_requests collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_gid: str = Field(..., description="Doctor's global ID (PRXDOC...)")
    doctor_id: str = Field(..., description="Doctor's MongoDB _id")
    doctor_username: str = Field(..., description="Doctor's username")
    organization_id: str = Field(..., description="Organization MongoDB _id")
    organization_gid: str = Field(..., description="Organization GID (PRXORG...)")
    organization_name: str = Field(..., description="Organization name (denormalized for display)")
    requested_by: str = Field(..., description="MRX admin username (from Proxzar sub)")
    status: str = Field(default=RequestStatus.PENDING)

    # Tracking who acted
    doctor_accepted: Optional[bool] = Field(None, description="True=accepted, False=rejected, None=pending")
    admin_accepted: Optional[bool] = Field(None, description="True=approved, False=rejected, None=pending")
    rejected_by: Optional[str] = Field(None, description="'doctor' or 'admin'")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    doctor_responded_at: Optional[datetime] = Field(None)
    admin_responded_at: Optional[datetime] = Field(None)
    admin_responded_by: Optional[str] = Field(None, description="DRX admin username who approved/rejected")
