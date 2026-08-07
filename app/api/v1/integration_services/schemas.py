"""
Integration Services — API Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateIntegrationServiceRequest(BaseModel):
    """Admin creates a new integration service"""
    service_name: str = Field(..., min_length=2, max_length=100, description="Human-friendly name")
    service_code: str = Field(..., min_length=2, max_length=50, description="Short code (e.g. ONBOARDING, MRX, OCR)")
    description: Optional[str] = Field(None, max_length=500)

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "service_name": "Voice Onboarding",
                "service_code": "ONBOARDING",
                "description": "Voice onboarding backend for doctor registration"
            }
        }


class CreateIntegrationServiceResponse(BaseModel):
    """Returned once on creation — contains the plain secret"""
    message: str
    service_id: str
    service_name: str
    service_code: str
    client_id: str
    client_secret: str = Field(..., description="Plain secret — shown only once. Store it securely.")
    status: str


class IntegrationServiceResponse(BaseModel):
    """Service in list/detail view — never includes secret"""
    id: str
    service_name: str
    service_code: str
    client_id: str
    status: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None


class IntegrationServiceListResponse(BaseModel):
    total: int
    services: List[IntegrationServiceResponse]


class RotateSecretResponse(BaseModel):
    """Returned on secret rotation — new plain secret shown once"""
    message: str
    client_id: str
    client_secret: str = Field(..., description="New plain secret — shown only once.")


class MessageResponse(BaseModel):
    message: str
