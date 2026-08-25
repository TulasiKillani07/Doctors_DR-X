"""
Integration Services — API Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateIntegrationServiceRequest(BaseModel):
    """Admin creates a new integration service"""
    service_name: str = Field(..., min_length=2, max_length=100, description="Human-friendly name")
    service_code: str = Field(..., min_length=2, max_length=50, description="Short code (e.g. DOBO, OCR)")
    description: Optional[str] = Field(None, max_length=500)
    proxzar_subject: Optional[str] = Field(None, description="Proxzar JWT 'sub' claim to match")
    proxzar_platform: Optional[str] = Field(None, description="Proxzar JWT 'platform' claim to match")
    permissions: List[str] = Field(default_factory=list, description="Allowed operations (e.g. ['doctor:create'])")

    class Config:
        extra = "forbid"
        json_schema_extra = {
            "example": {
                "service_name": "Voice Onboarding (DOBO)",
                "service_code": "DOBO",
                "description": "Voice onboarding backend for doctor registration",
                "proxzar_subject": "rx_integration",
                "proxzar_platform": "dobo",
                "permissions": ["doctor:create"]
            }
        }


class CreateIntegrationServiceResponse(BaseModel):
    """Returned on creation"""
    message: str
    service_id: str
    service_name: str
    service_code: str
    status: str


class IntegrationServiceResponse(BaseModel):
    """Service in list/detail view"""
    id: str
    service_name: str
    service_code: str
    status: str
    description: Optional[str] = None
    authentication_provider: str = "PROXZAR"
    proxzar_subject: Optional[str] = None
    proxzar_platform: Optional[str] = None
    permissions: List[str] = []
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None


class IntegrationServiceListResponse(BaseModel):
    total: int
    services: List[IntegrationServiceResponse]


class MessageResponse(BaseModel):
    message: str
