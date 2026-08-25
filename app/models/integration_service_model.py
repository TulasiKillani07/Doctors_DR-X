"""
Integration Service model — trusted backend services that can authenticate with DRX.
Collection: integration_services

Authentication is via Proxzar JWT verified using JWKS.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class IntegrationServiceInDB(BaseModel):
    """Write model for integration_services collection"""
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(..., min_length=2, max_length=100)
    service_code: str = Field(..., min_length=2, max_length=50)
    status: str = Field(default="ACTIVE", description="ACTIVE or INACTIVE")
    description: Optional[str] = Field(None, max_length=500)

    # Proxzar authentication
    authentication_provider: str = Field(default="PROXZAR", description="PROXZAR")
    proxzar_subject: Optional[str] = Field(None, description="Proxzar JWT 'sub' claim to match (e.g. rx_integration)")
    proxzar_platform: Optional[str] = Field(None, description="Proxzar JWT 'platform' claim to match (e.g. dobo)")
    permissions: List[str] = Field(default_factory=list, description="Allowed operations (e.g. ['doctor:create'])")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field(None, description="Updated on every successful authentication")
