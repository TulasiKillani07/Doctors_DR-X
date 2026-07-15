"""
Notification Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from app.core.auth import require_doctor
from app.api.v1.notifications import service

router = APIRouter()


@router.get("", summary="Get My Notifications")
async def get_notifications(
    is_read: Optional[bool] = Query(None, description="Filter: true=read, false=unread, None=all"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get logged-in doctor's notifications.

    **Access:** Doctor only

    **Query Params:** `is_read` (true/false/omit), `skip`, `limit`

    **Response:**
    ```json
    {
      "total": 5,
      "notifications": [
        {
          "id": "...",
          "title": "Organization Invite",
          "message": "XYZ Pharma has invited you to join their network",
          "type": "org_invite",
          "is_read": false,
          "created_at": "2026-07-15T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_notifications(current_user["_id"], is_read, skip, limit)


@router.get("/count", summary="Unread Notification Count")
async def get_unread_count(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get unread notification count (for badge display).

    **Access:** Doctor only

    **Response:**
    ```json
    { "unread_count": 3 }
    ```
    """
    return await service.get_unread_count(current_user["_id"])


@router.put("/{notification_id}/read", summary="Mark as Read")
async def mark_as_read(
    notification_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Mark a single notification as read.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Notification marked as read" }
    ```
    """
    return await service.mark_as_read(notification_id, current_user["_id"])


@router.put("/read-all", summary="Mark All as Read")
async def mark_all_as_read(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Mark all notifications as read.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "5 notifications marked as read" }
    ```
    """
    return await service.mark_all_as_read(current_user["_id"])


@router.delete("/{notification_id}", summary="Delete Notification")
async def delete_notification(
    notification_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Delete a notification.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Notification deleted" }
    ```
    """
    return await service.delete_notification(notification_id, current_user["_id"])
