"""
Organization request/response schemas
"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.utils.validators import (
    validate_username as _v_username,
    validate_password as _v_password,
    validate_full_name as _v_fullname,
    validate_phone as _v_phone,
    validate_email_domain as _v_email_domain,
)


class OrganizationCreateRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=200)
    mrx_url: str = Field(..., min_length=10, max_length=500, description="Organization's MRX backend URL (required for communication)")
    logo: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    org_admin: str = Field(..., description="Organization admin full name (8-64 characters)")
    admin_username: str = Field(..., description="Org admin username (6-16 chars, letters/numbers/underscore)")
    admin_email: EmailStr = Field(..., description="Org admin email")
    admin_phone: Optional[str] = Field(None, description="E.164 format, e.g. +919848012345")
    admin_password: str = Field(..., description="8-24 chars, 1 upper, 1 lower, 1 number, 1 symbol")
    address: Optional[str] = Field(None, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)

    @field_validator("org_admin")
    @classmethod
    def _admin_name(cls, v: str) -> str:
        return _v_fullname(v)

    @field_validator("admin_username")
    @classmethod
    def _admin_username(cls, v: str) -> str:
        return _v_username(v)

    @field_validator("admin_password")
    @classmethod
    def _admin_password(cls, v: str) -> str:
        return _v_password(v)

    @field_validator("admin_email")
    @classmethod
    def _admin_email(cls, v: str) -> str:
        return _v_email_domain(v)

    @field_validator("admin_phone")
    @classmethod
    def _admin_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return _v_phone(v)


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
