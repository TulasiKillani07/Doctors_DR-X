"""
Notifications service — DRX Doctor Platform
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.models.social_models import NotificationInDB


async def get_notifications(
    doctor_id: str,
    is_read: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """Get doctor's notifications"""
    db = get_database()

    query = {"user_id": doctor_id}
    if is_read is not None:
        query["is_read"] = is_read

    total = await db.notifications.count_documents(query)
    notifications = await db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for n in notifications:
        n["id"] = str(n.pop("_id"))

    return {"total": total, "notifications": notifications}


async def get_unread_count(doctor_id: str) -> Dict[str, int]:
    """Get unread notification count"""
    db = get_database()
    count = await db.notifications.count_documents({"user_id": doctor_id, "is_read": False})
    return {"unread_count": count}


async def mark_as_read(notification_id: str, doctor_id: str) -> Dict[str, str]:
    """Mark a single notification as read"""
    db = get_database()

    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notification ID")

    result = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": doctor_id},
        {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return {"message": "Notification marked as read"}


async def mark_all_as_read(doctor_id: str) -> Dict[str, str]:
    """Mark all notifications as read"""
    db = get_database()

    result = await db.notifications.update_many(
        {"user_id": doctor_id, "is_read": False},
        {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
    )

    return {"message": f"{result.modified_count} notifications marked as read"}


async def delete_notification(notification_id: str, doctor_id: str) -> Dict[str, str]:
    """Delete a notification"""
    db = get_database()

    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notification ID")

    result = await db.notifications.delete_one(
        {"_id": ObjectId(notification_id), "user_id": doctor_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    return {"message": "Notification deleted"}


async def create_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "general",
    metadata: Optional[Dict] = None
) -> str:
    """Create a notification (internal helper — used by other services)"""
    db = get_database()

    notification = NotificationInDB(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        metadata=metadata or {},
        is_read=False,
        created_at=datetime.utcnow()
    )

    result = await db.notifications.insert_one(notification.model_dump())
    return str(result.inserted_id)
