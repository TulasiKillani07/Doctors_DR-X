"""
Platform Admin model — internal staff who manage the Doctor Platform
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class AdminUserInDB(BaseModel):
    """Write model for admin_users collection"""
    username: str = Field(..., min_length=3, max_length=30, description="Unique username")
    email: EmailStr = Field(..., description="Admin email (unique)")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    role: str = Field(default="PLATFORM_ADMIN", description="Always PLATFORM_ADMIN")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field(None)

    class Config:
        extra = "forbid"
