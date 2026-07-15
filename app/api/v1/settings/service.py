"""
Doctor Settings service — DRX Doctor Platform
"""

from datetime import datetime
from typing import Dict, Any
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.core.security import verify_password, hash_password


async def change_password(current_password: str, new_password: str, current_user: Dict) -> Dict[str, str]:
    """Change doctor's password"""
    db = get_database()

    doctor = await db.doctors.find_one({"_id": ObjectId(current_user["_id"])})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # Verify current password
    if not verify_password(current_password, doctor["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    # Hash and save new password
    new_hash = hash_password(new_password)
    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": {"password_hash": new_hash, "updated_at": datetime.utcnow()}}
    )

    return {"message": "Password changed successfully"}


async def get_preferences(current_user: Dict) -> Dict[str, Any]:
    """Get doctor's preferences/settings"""
    db = get_database()

    doctor = await db.doctors.find_one(
        {"_id": ObjectId(current_user["_id"])},
        {"preferences": 1}
    )

    # Default preferences if none set
    defaults = {
        "language": "en",
        "notifications_enabled": True,
        "email_notifications": True,
        "sms_notifications": False,
        "profile_visibility": "public",  # public, connections_only, private
        "show_phone": False,
        "show_email": True,
    }

    prefs = doctor.get("preferences", {}) if doctor else {}
    # Merge defaults with stored preferences
    merged = {**defaults, **prefs}

    return merged


async def update_preferences(preferences: Dict[str, Any], current_user: Dict) -> Dict[str, str]:
    """Update doctor's preferences"""
    db = get_database()

    allowed_keys = {
        "language", "notifications_enabled", "email_notifications",
        "sms_notifications", "profile_visibility", "show_phone", "show_email"
    }

    # Filter to only allowed keys
    update_prefs = {k: v for k, v in preferences.items() if k in allowed_keys}

    if not update_prefs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid preferences to update")

    # Validate profile_visibility
    if "profile_visibility" in update_prefs:
        if update_prefs["profile_visibility"] not in ("public", "connections_only", "private"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="profile_visibility must be: public, connections_only, or private")

    # Store as nested object
    set_fields = {f"preferences.{k}": v for k, v in update_prefs.items()}
    set_fields["updated_at"] = datetime.utcnow()

    await db.doctors.update_one(
        {"_id": ObjectId(current_user["_id"])},
        {"$set": set_fields}
    )

    return {"message": "Preferences updated successfully"}
