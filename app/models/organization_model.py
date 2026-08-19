"""
Organization model — pharmaceutical companies registered on our platform
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
import random


def generate_org_gid() -> str:
    """Generate unique organization GID: PRXORG + 6 random digits"""
    return f"PRXORG{random.randint(100000, 999999)}"


class OrganizationInDB(BaseModel):
    """Write model for organizations collection"""
    organization_gid: str = Field(default_factory=generate_org_gid, description="Global org identifier (e.g. PRXORG482915). Immutable.")
    organization_name: str = Field(..., min_length=2, max_length=200, description="Company name")
    logo: Optional[str] = Field(None, description="Logo URL")
    contact_email: Optional[EmailStr] = Field(None, description="Organization contact email")
    contact_phone: Optional[str] = Field(None, description="Organization contact phone")
    org_admin: str = Field(..., max_length=100, description="Organization admin name")
    admin_username: str = Field(..., max_length=30, description="Organization admin username")
    admin_email: EmailStr = Field(..., description="Admin email")
    admin_phone: Optional[str] = Field(None, description="Admin phone")
    address: Optional[str] = Field(None, max_length=500, description="Address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State")
    country: Optional[str] = Field(None, max_length=100, description="Country")
    pincode: Optional[str] = Field(None, max_length=20, description="Pincode")
    # Integration (DRX → MRX direction) — only mrx_url needed per org
    mrx_url: Optional[str] = Field(None, max_length=500, description="Organization's MRX backend URL")
    status: str = Field(default="ACTIVE", description="ACTIVE or INACTIVE")
    created_by: str = Field(..., description="Admin user ID who created this org")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"
