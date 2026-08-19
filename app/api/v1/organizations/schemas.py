"""
Organization request/response schemas
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class OrganizationCreateRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=200)
    mrx_url: str = Field(..., min_length=10, max_length=500, description="Organization's MRX backend URL (required for communication)")
    logo: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    org_admin: str = Field(..., min_length=2, max_length=100, description="Organization admin full name")
    admin_username: str = Field(..., min_length=3, max_length=30, description="Org admin username (3-30 chars, alphanumeric + underscores)")
    admin_email: EmailStr = Field(..., description="Org admin email")
    admin_phone: Optional[str] = None
    admin_password: str = Field(..., min_length=8, max_length=64, description="Org admin password")
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)


class OrganizationUpdateRequest(BaseModel):
    organization_name: Optional[str] = Field(None, min_length=2, max_length=200)
    mrx_url: Optional[str] = Field(None, min_length=10, max_length=500, description="Update MRX backend URL")
    logo: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    org_admin: Optional[str] = Field(None, max_length=100)
    admin_email: Optional[EmailStr] = None
    admin_phone: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, description="ACTIVE or INACTIVE")


class OrganizationResponse(BaseModel):
    id: str
    organization_gid: str
    organization_name: str
    mrx_url: Optional[str] = None
    logo: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    org_admin: Optional[str] = None
    admin_email: Optional[str] = None
    admin_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class OrganizationListResponse(BaseModel):
    total: int
    organizations: List[OrganizationResponse]


class MessageResponse(BaseModel):
    message: str
    organization_id: Optional[str] = None
    organization_gid: Optional[str] = None
