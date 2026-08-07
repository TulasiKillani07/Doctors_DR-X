"""
Integration Service model — trusted backend services that can authenticate with DRX.
Collection: integration_services
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class IntegrationServiceInDB(BaseModel):
    """Write model for integration_services collection"""
    model_config = ConfigDict(extra="forbid")

    service_name: str = Field(..., min_length=2, max_length=100)
    service_code: str = Field(..., min_length=2, max_length=50)
    client_id: str = Field(..., description="Auto-generated unique client identifier")
    client_secret_hash: str = Field(..., description="Bcrypt hash of client_secret — never store plain")
    status: str = Field(default="ACTIVE", description="ACTIVE or INACTIVE")
    description: Optional[str] = Field(None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = Field(None, description="Updated on every successful token issue")
