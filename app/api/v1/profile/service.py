"""
Profile service for DRX Doctor Platform
"""

from datetime import datetime
from typing import Dict, Any
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


async def get_my_profile(current_user: Dict) -> Dict[str, Any]:
    """
    Get current doctor's complete profile.
    """
    db = get_database()
    role = current_user["role"]

    if role == "DOCTOR":
        doctor = await db.doctors.find_one({"_id": ObjectId(current_user["_id"])})
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        return {
            "user_id": str(doctor["_id"]),
            "doctor_gid": doctor.get("doctor_gid", ""),
            "email": doctor.get("email", ""),
            "phone": doctor.get("phone", ""),
            "name": doctor.get("name", ""),
            "role": "DOCTOR",
            # Professional
            "specialization": doctor.get("specialization"),
            "license_number": doctor.get("license_number"),
            "experience_years": doctor.get("experience_years"),
            "qualification": doctor.get("qualification"),
            # Personal
            "bio": doctor.get("bio"),
            "avatar_url": doctor.get("avatar_url"),
            "location": doctor.get("location"),
            "city": doctor.get("city"),
            "state": doctor.get("state"),
            "country": doctor.get("country"),
            # Status
            "is_active": doctor.get("is_active", True),
            "is_email_verified": doctor.get("is_email_verified", False),
            "created_at": doctor.get("created_at"),
            "updated_at": doctor.get("updated_at"),
        }

    elif role == "PLATFORM_ADMIN":
        admin = await db.admin_users.find_one({"_id": ObjectId(current_user["_id"])})
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        return {
            "user_id": str(admin["_id"]),
            "doctor_gid": None,
            "email": admin.get("email", ""),
            "phone": admin.get("phone", ""),
            "name": admin.get("name", ""),
            "role": "PLATFORM_ADMIN",
            "specialization": None,
            "license_number": None,
            "experience_years": None,
            "qualification": None,
            "bio": None,
            "avatar_url": None,
            "location": None,
            "city": None,
            "state": None,
            "country": None,
            "is_active": admin.get("is_active", True),
            "is_email_verified": None,
            "created_at": admin.get("created_at"),
            "updated_at": admin.get("updated_at"),
        }

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid role")


async def update_my_profile(update_data: Dict[str, Any], current_user: Dict) -> Dict[str, str]:
    """
    Update current doctor's profile.
    Only doctors can update their own profile via this endpoint.
    """
    db = get_database()
    role = current_user["role"]

    if role != "DOCTOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can update their profile here"
        )

    # Only allow valid doctor profile fields
    allowed_fields = {
        "name", "phone", "specialization", "license_number",
        "experience_years", "qualification", "bio", "avatar_url",
        "location", "city", "state", "country"
    }

    update_doc = {}
    for field, value in update_data.items():
        if field in allowed_fields and value is not None:
            update_doc[field] = value

    if not update_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    update_doc["updated_at"] = datetime.utcnow()

    result = await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": update_doc}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    return {"message": "Profile updated successfully"}


# ══════════════════════════════════════════════════════════════
# Doctor Location Self-Service
# ══════════════════════════════════════════════════════════════

import uuid


VALID_PRIORITIES = {"PRIMARY", "SECONDARY", "OTHER"}
VALID_FACILITY_TYPES = {"HOSPITAL", "CLINIC", "POLYCLINIC", "MEDICAL_CENTER", "INSTITUTION_OR_MEDICAL_COLLEGE", "OTHER"}


async def get_my_locations(current_user: Dict) -> Dict[str, Any]:
    """Get logged-in doctor's locations"""
    db = get_database()
    doctor = await db.doctors.find_one(
        {"_id": ObjectId(current_user["_id"])},
        {"locations": 1}
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    locations = doctor.get("locations", [])
    return {"total": len(locations), "locations": locations}


async def add_my_location(location_data: Dict[str, Any], current_user: Dict) -> Dict[str, Any]:
    """Doctor adds a practice location to their own profile"""
    db = get_database()

    location = dict(location_data)
    location["location_id"] = str(uuid.uuid4())
    location.setdefault("location_priority", "OTHER")
    location.setdefault("status", "ACTIVE")
    location["added_at"] = datetime.utcnow()

    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$push": {"locations": location},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return {"message": "Location added successfully", "location_id": location["location_id"]}


async def update_my_location(location_id: str, update_data: Dict[str, Any], current_user: Dict) -> Dict[str, str]:
    """Doctor updates one of their own locations"""
    db = get_database()

    # Whitelist: only these fields can be updated by the doctor
    allowed_location_fields = {
        "location_name", "facility_type", "facility_type_other", "address", "area",
        "country", "state", "district", "city", "postcode", "latitude", "longitude",
        "location_source", "status", "location_priority"
    }

    update_fields = {}
    for key, value in update_data.items():
        if value is not None and key in allowed_location_fields:
            update_fields[f"locations.$.{key}"] = value

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    update_fields["updated_at"] = datetime.utcnow()

    result = await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"]), "locations.location_id": location_id},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    return {"message": "Location updated successfully"}


async def delete_my_location(location_id: str, current_user: Dict) -> Dict[str, str]:
    """Doctor removes a location from their profile"""
    db = get_database()

    result = await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$pull": {"locations": {"location_id": location_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    return {"message": "Location removed successfully"}


async def set_location_priority(location_id: str, new_priority: str, current_user: Dict) -> Dict[str, str]:
    """
    Set a location's priority (PRIMARY / SECONDARY / OTHER).

    If set to PRIMARY, any existing PRIMARY location is demoted to SECONDARY
    (only one PRIMARY at a time).
    """
    new_priority = (new_priority or "").upper()
    if new_priority not in VALID_PRIORITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"priority must be one of {VALID_PRIORITIES}"
        )

    db = get_database()

    doctor = await db.doctors.find_one(
        {"_id": ObjectId(current_user["_id"]), "locations.location_id": location_id},
        {"locations": 1}
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    locations = doctor.get("locations", [])

    # Apply new priorities
    for loc in locations:
        if loc.get("location_id") == location_id:
            loc["location_priority"] = new_priority
        elif new_priority == "PRIMARY" and loc.get("location_priority") == "PRIMARY":
            # Demote the old primary
            loc["location_priority"] = "SECONDARY"

    set_fields = {"locations": locations, "updated_at": datetime.utcnow()}

    # If new primary, promote its geography to top-level
    if new_priority == "PRIMARY":
        primary = next((l for l in locations if l.get("location_id") == location_id), None)
        if primary:
            set_fields["city"] = primary.get("city")
            set_fields["state"] = primary.get("state")
            set_fields["country"] = primary.get("country")

    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": set_fields}
    )

    return {"message": f"Location priority set to {new_priority}"}
