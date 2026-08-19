"""
Auth service for DRX Doctor Platform

User authentication is via Proxzar OAuth only.
This service handles user provisioning (registration/creation).
Login functions are deprecated — kept as stubs for reference.
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.core.security import hash_password
from app.models.admin_model import AdminUserInDB
from app.models.doctor_model import DoctorInDB


async def create_admin(name: str, email: str, username: str, password: str) -> Dict[str, Any]:
    """Create a new platform admin"""
    db = get_database()

    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if await db.admin_users.find_one({"username": username}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    admin = AdminUserInDB(
        username=username,
        email=email,
        password_hash=hash_password(password),
        name=name,
        role="PLATFORM_ADMIN",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.admin_users.insert_one(admin.model_dump())

    return {
        "message": "Platform admin created successfully",
        "user_id": str(result.inserted_id)
    }


async def doctor_register(name: str, email: str, phone: str, username: str, password: str) -> Dict[str, Any]:
    """Doctor self-registration"""
    from app.models.doctor_model import generate_doctor_gid
    db = get_database()

    if await db.doctors.find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if await db.doctors.find_one({"phone": phone}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already registered")

    if await db.doctors.find_one({"username": username}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required")

    # Generate unique GID (retry on collision)
    doctor_gid = generate_doctor_gid()
    while await db.doctors.find_one({"doctor_gid": doctor_gid}):
        doctor_gid = generate_doctor_gid()

    doctor = DoctorInDB(
        doctor_gid=doctor_gid,
        username=username,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        name=name,
        is_active=True,
        is_email_verified=False,
        is_phone_verified=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.doctors.insert_one(doctor.model_dump())

    return {
        "message": "Doctor registered successfully",
        "user_id": str(result.inserted_id),
        "doctor_gid": doctor_gid
    }
