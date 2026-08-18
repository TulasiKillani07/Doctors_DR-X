"""
Doctor management service — single add + bulk upload
"""

import re
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, UploadFile, status
import pandas as pd
from io import BytesIO
from bson import ObjectId
from app.database import get_database
from app.core.security import hash_password
from app.config import settings
from app.models.doctor_model import DoctorInDB, generate_doctor_gid


def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Accept 10-digit numbers or with country code (e.g. +91XXXXXXXXXX)"""
    cleaned = re.sub(r'[^0-9]', '', str(phone))
    return len(cleaned) == 10 or len(cleaned) == 12


async def add_single_doctor(data: Dict[str, Any], return_existing: bool = False) -> Dict[str, Any]:
    """
    Single source of truth for doctor creation.
    Called by both admin endpoint and integration endpoint.

    Args:
        data: Doctor fields (name, email, phone, specialization, etc.)
        return_existing: If True, returns existing doctor info instead of raising 400 on duplicate.
                         Used by integration (MRX auto-sync, voice onboarding).
    """
    db = get_database()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    phone = data.get("phone", "").strip()

    # Validate required
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is required")
    if not email or not validate_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid email is required")
    if not phone or not validate_phone(phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Valid 10-digit phone is required")

    # Check duplicates
    existing_email = await db.doctors.find_one({"email": email})
    if existing_email:
        if return_existing:
            return {"status": "exists", "doctor_gid": existing_email.get("doctor_gid", ""), "doctor_id": str(existing_email["_id"]), "message": "Doctor already exists on DRX"}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    existing_phone = await db.doctors.find_one({"phone": phone})
    if existing_phone:
        if return_existing:
            return {"status": "exists", "doctor_gid": existing_phone.get("doctor_gid", ""), "doctor_id": str(existing_phone["_id"]), "message": "Doctor with this phone already exists on DRX"}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number already registered")

    # Generate unique GID
    doctor_gid = generate_doctor_gid()
    while await db.doctors.find_one({"doctor_gid": doctor_gid}):
        doctor_gid = generate_doctor_gid()

    # Username is required
    username = data.get("username", "").strip().lower()
    if not username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required")

    # Validate format
    import re as _re
    if not _re.match(r'^[a-z0-9_]{3,30}$', username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be 3-30 characters, only lowercase letters, numbers, and underscores")

    # Check uniqueness
    if await db.doctors.find_one({"username": username}):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    # Build doctor document
    doctor = DoctorInDB(
        doctor_gid=doctor_gid,
        username=username,
        email=email,
        phone=phone,
        password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
        name=name,
        specialization=data.get("specialization"),
        hospital=data.get("hospital"),
        qualification=data.get("qualification"),
        license_number=data.get("license_number"),
        is_active=True,
        is_email_verified=False,
        is_phone_verified=False,
        registered_via=data.get("registered_via", "drx_admin"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.doctors.insert_one(doctor.model_dump())

    return {
        "status": "created",
        "message": "Doctor added successfully",
        "doctor_id": str(result.inserted_id),
        "doctor_gid": doctor_gid,
        "default_password": settings.DEFAULT_USER_PASSWORD
    }


async def bulk_upload_doctors(file: UploadFile, admin_user: Dict) -> Dict[str, Any]:
    """Bulk upload doctors from CSV"""
    db = get_database()

    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files supported")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")

    # Parse file
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Clean column names
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

    # Validate required columns
    required = ["name", "username", "email", "phone"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing)}")

    if len(df) > 200:
        raise HTTPException(status_code=400, detail=f"Max 200 rows per upload. File has {len(df)} rows.")

    successful = 0
    failed = 0
    errors = []

    for idx, row in df.iterrows():
        row_number = idx + 2  # 1-indexed + header

        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
        email = str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else ''
        phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
        username = str(row.get('username', '')).strip().lower() if pd.notna(row.get('username')) else ''

        # Validate
        if not name:
            errors.append({"row": row_number, "email": email, "error": "Name is required"})
            failed += 1
            continue

        if not username or not re.match(r'^[a-z0-9_]{3,30}$', username):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Username is required (3-30 chars, lowercase letters/numbers/underscores)"})
            failed += 1
            continue

        if not email or not validate_email(email):
            errors.append({"row": row_number, "name": name, "error": "Invalid or missing email"})
            failed += 1
            continue

        # Clean phone
        phone_cleaned = re.sub(r'[^0-9]', '', phone)
        if len(phone_cleaned) > 10:
            phone_cleaned = phone_cleaned[-10:]

        if not validate_phone(phone_cleaned):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Phone must be 10 digits"})
            failed += 1
            continue

        # Check duplicates in DB
        if await db.doctors.find_one({"email": email}):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Email already exists"})
            failed += 1
            continue

        if await db.doctors.find_one({"phone": phone_cleaned}):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Phone already exists"})
            failed += 1
            continue

        # Generate unique GID
        doctor_gid = generate_doctor_gid()
        while await db.doctors.find_one({"doctor_gid": doctor_gid}):
            doctor_gid = generate_doctor_gid()

        # Check username uniqueness
        if await db.doctors.find_one({"username": username}):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Username already taken"})
            failed += 1
            continue

        # Create doctor
        try:
            doctor = DoctorInDB(
                doctor_gid=doctor_gid,
                username=username,
                email=email,
                phone=phone_cleaned,
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                name=name,
                is_active=True,
                is_email_verified=False,
                is_phone_verified=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await db.doctors.insert_one(doctor.model_dump())
            successful += 1
        except Exception as e:
            errors.append({"row": row_number, "name": name, "email": email, "error": f"DB error: {str(e)}"})
            failed += 1

    message = f"Bulk upload completed. {successful} doctors added"
    if failed > 0:
        message += f", {failed} rows failed."
    else:
        message += " successfully."

    return {
        "total_rows": len(df),
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "message": message
    }


# ══════════════════════════════════════════════════════════════
# Doctor CRUD (Admin)
# ══════════════════════════════════════════════════════════════

from bson import ObjectId
from fastapi import status
import uuid


async def get_doctor_by_id(doctor_id: str) -> Dict[str, Any]:
    """Get a single doctor by ID (admin view)"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    doctor["id"] = str(doctor.pop("_id"))
    doctor.pop("password_hash", None)
    return doctor


async def list_all_doctors(search: str = None, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
    """List doctors with optional search, pagination"""
    db = get_database()

    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"doctor_gid": {"$regex": search, "$options": "i"}},
            {"specialization": {"$regex": search, "$options": "i"}}
        ]

    total = await db.doctors.count_documents(query)
    doctors = await db.doctors.find(query, {"password_hash": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for doc in doctors:
        doc["id"] = str(doc.pop("_id"))

    return {"total": total, "doctors": doctors}


async def update_doctor_by_admin(doctor_id: str, update_data: Dict[str, Any]) -> Dict[str, str]:
    """Admin updates a doctor's profile"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # Filter out None values
    update_doc = {k: v for k, v in update_data.items() if v is not None}
    if not update_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    update_doc["updated_at"] = datetime.utcnow()

    await db.doctors.update_one({"_id": ObjectId(doctor_id)}, {"$set": update_doc})
    return {"message": "Doctor updated successfully"}


# ══════════════════════════════════════════════════════════════
# Location Management
# ══════════════════════════════════════════════════════════════

async def add_doctor_location(doctor_id: str, location_data: Dict[str, Any], admin_user: Dict) -> Dict[str, Any]:
    """Add a practice location to a doctor"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    location_id = str(uuid.uuid4())[:8]

    location = {
        "id": location_id,
        "type": location_data.get("type", "hospital"),
        "name": location_data["name"],
        "address": location_data["address"],
        "country": location_data["country"],
        "state": location_data["state"],
        "district": location_data["district"],
        "city": location_data["city"],
        "area": location_data["area"],
        "latitude": location_data["latitude"],
        "longitude": location_data["longitude"],
        "is_active": True,
        "geofence_radius": location_data.get("geofence_radius", 100),
        "added_by": str(admin_user["_id"]),
        "added_at": datetime.utcnow()
    }

    await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {
            "$push": {"locations": location},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return {"message": "Location added successfully", "location_id": location_id}


async def get_doctor_locations(doctor_id: str) -> Dict[str, Any]:
    """Get all locations for a doctor"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)}, {"locations": 1})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    locations = doctor.get("locations", [])
    return {"total": len(locations), "locations": locations}


async def update_doctor_location(doctor_id: str, location_id: str, update_data: Dict[str, Any]) -> Dict[str, str]:
    """Update a specific location on a doctor"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    # Build $set for nested location fields
    update_fields = {}
    for key, value in update_data.items():
        if value is not None:
            update_fields[f"locations.$.{key}"] = value

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    update_fields["updated_at"] = datetime.utcnow()

    result = await db.doctors.update_one(
        {"_id": ObjectId(doctor_id), "locations.id": location_id},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor or location not found")

    return {"message": "Location updated successfully"}


async def delete_doctor_location(doctor_id: str, location_id: str) -> Dict[str, str]:
    """Remove a location from a doctor"""
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    result = await db.doctors.update_one(
        {"_id": ObjectId(doctor_id)},
        {
            "$pull": {"locations": {"id": location_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    return {"message": "Location removed successfully"}
