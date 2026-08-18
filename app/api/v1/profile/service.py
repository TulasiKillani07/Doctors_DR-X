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
            "hospital": doctor.get("hospital"),
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
            "is_phone_verified": doctor.get("is_phone_verified", False),
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
            "hospital": None,
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
            "is_phone_verified": None,
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
        "name", "phone", "specialization", "hospital", "license_number",
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


async def get_my_locations(current_user: Dict) -> Dict[str, Any]:
    """Get logged-in doctor's locations"""
    db = get_database()
    doctor = await db.doctors.find_one(
        {"_id": ObjectId(current_user["_id"])},
        {"locations": 1, "primary_location_id": 1}
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    locations = doctor.get("locations", [])
    primary_id = doctor.get("primary_location_id")

    # Add is_primary flag
    for loc in locations:
        loc["is_primary"] = (loc.get("id") == primary_id)

    return {"total": len(locations), "locations": locations}


async def add_my_location(location_data: Dict[str, Any], current_user: Dict) -> Dict[str, Any]:
    """Doctor adds a practice location to their own profile"""
    db = get_database()

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
        "added_by": "self",
        "added_at": datetime.utcnow()
    }

    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {
            "$push": {"locations": location},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return {"message": "Location added successfully"}


async def update_my_location(location_id: str, update_data: Dict[str, Any], current_user: Dict) -> Dict[str, str]:
    """Doctor updates one of their own locations"""
    db = get_database()

    # Whitelist: only these fields can be updated by the doctor
    allowed_location_fields = {
        "name", "address", "country", "state", "district", "city", "area",
        "latitude", "longitude", "type", "geofence_radius", "is_active"
    }

    update_fields = {}
    for key, value in update_data.items():
        if value is not None and key in allowed_location_fields:
            update_fields[f"locations.$.{key}"] = value

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

    update_fields["updated_at"] = datetime.utcnow()

    result = await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"]), "locations.id": location_id},
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
            "$pull": {"locations": {"id": location_id}},
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # If this was the primary, clear primary_location_id
    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"]), "primary_location_id": location_id},
        {"$unset": {"primary_location_id": ""}}
    )

    return {"message": "Location removed successfully"}


async def set_primary_location(location_id: str, current_user: Dict) -> Dict[str, str]:
    """Set a location as primary"""
    db = get_database()

    # Verify the location exists on this doctor
    doctor = await db.doctors.find_one(
        {"_id": ObjectId(current_user["_id"]), "locations.id": location_id}
    )
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"primary_location_id": location_id, "updated_at": datetime.utcnow()}}
    )

    return {"message": "Primary location updated"}
