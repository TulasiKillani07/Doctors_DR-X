"""
Auth service for DRX Doctor Platform
"""

from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.core.security import hash_password, verify_password, create_access_token
from app.models.admin_model import AdminUserInDB
from app.models.doctor_model import DoctorInDB


async def create_admin(name: str, email: str, password: str = None) -> Dict[str, Any]:
    """Create a new platform admin"""
    from app.config import settings
    db = get_database()

    if await db.admin_users.find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    final_password = password or settings.DEFAULT_USER_PASSWORD

    admin = AdminUserInDB(
        email=email,
        password_hash=hash_password(final_password),
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


async def admin_login(email: str, password: str) -> Dict[str, Any]:
    """Platform admin login"""
    db = get_database()
    admin = await db.admin_users.find_one({"email": email})

    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(password, admin["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not admin.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    # Update last_login
    await db.admin_users.update_one(
        {"_id": admin["_id"]},
        {"$set": {"last_login_at": datetime.utcnow()}}
    )

    token = create_access_token({"sub": str(admin["_id"]), "role": "PLATFORM_ADMIN", "iss": "DRX", "aud": "MRX"})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "PLATFORM_ADMIN",
        "user": {
            "id": str(admin["_id"]),
            "email": admin["email"],
            "name": admin["name"]
        }
    }


async def doctor_register(name: str, email: str, phone: str, username: str, password: str = None) -> Dict[str, Any]:
    """Doctor self-registration"""
    from app.config import settings
    from app.models.doctor_model import generate_doctor_gid
    db = get_database()

    if await db.doctors.find_one({"email": email}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if await db.doctors.find_one({"phone": phone}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone already registered")

    if await db.doctors.find_one({"username": username}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    final_password = password or settings.DEFAULT_USER_PASSWORD

    # Generate unique GID (retry on collision)
    doctor_gid = generate_doctor_gid()
    while await db.doctors.find_one({"doctor_gid": doctor_gid}):
        doctor_gid = generate_doctor_gid()

    doctor = DoctorInDB(
        doctor_gid=doctor_gid,
        username=username,
        email=email,
        phone=phone,
        password_hash=hash_password(final_password),
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


async def doctor_login(identifier: str, password: str) -> Dict[str, Any]:
    """Doctor login — accepts email, username, or doctor_gid"""
    db = get_database()

    # Determine if identifier is email, GID, or username
    if "@" in identifier:
        doctor = await db.doctors.find_one({"email": identifier})
    elif identifier.upper().startswith("PRXDOC"):
        doctor = await db.doctors.find_one({"doctor_gid": identifier})
    else:
        # Treat as username (stored lowercase)
        doctor = await db.doctors.find_one({"username": identifier.lower()})

    if not doctor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(password, doctor["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not doctor.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    # Update last_login
    await db.doctors.update_one(
        {"_id": doctor["_id"]},
        {"$set": {"last_login_at": datetime.utcnow()}}
    )

    token = create_access_token({"sub": str(doctor["_id"]), "role": "DOCTOR", "iss": "DRX", "aud": "MRX"})

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "DOCTOR",
        "user": {
            "id": str(doctor["_id"]),
            "doctor_gid": doctor["doctor_gid"],
            "email": doctor["email"],
            "name": doctor["name"]
        }
    }
