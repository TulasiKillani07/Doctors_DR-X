"""
Doctor-Organization relationship schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateRelationshipRequest(BaseModel):
    doctor_id: str = Field(..., description="Doctor MongoDB _id")
    organization_id: str = Field(..., description="Organization MongoDB _id")


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="New status: ACTIVE, REJECTED, REMOVED")


class DoctorOrganizationResponse(BaseModel):
    id: str
    doctor_id: str
    organization_id: str
    status: str
    requested_by: str
    requested_at: datetime
    responded_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    removed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DoctorOrganizationListResponse(BaseModel):
    total: int
    relationships: List[DoctorOrganizationResponse]


class MessageResponse(BaseModel):
    message: str
    relationship_id: Optional[str] = None
