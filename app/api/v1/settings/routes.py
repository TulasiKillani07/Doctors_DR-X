"""
Doctor Settings Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends
from typing import Dict
from pydantic import BaseModel, Field
from typing import Optional
from app.core.auth import require_doctor
from app.api.v1.settings import service

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=72)


class UpdatePreferencesRequest(BaseModel):
    language: Optional[str] = Field(None, max_length=10, description="Language code: en, hi, te, etc.")
    notifications_enabled: Optional[bool] = None
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    profile_visibility: Optional[str] = Field(None, description="public, connections_only, or private")
    show_phone: Optional[bool] = None
    show_email: Optional[bool] = None


@router.post("/change-password", summary="Change Password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Change the logged-in doctor's password.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "current_password": "Welcome@123",
      "new_password": "MyNewSecure@456"
    }
    ```

    **Response:**
    ```json
    { "message": "Password changed successfully" }
    ```

    **Rules:**
    - Must provide correct current password
    - New password: 8-72 characters
    """
    return await service.change_password(request.current_password, request.new_password, current_user)


@router.get("/preferences", summary="Get My Preferences")
async def get_preferences(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get the doctor's preferences/settings.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "language": "en",
      "notifications_enabled": true,
      "email_notifications": true,
      "sms_notifications": false,
      "profile_visibility": "public",
      "show_phone": false,
      "show_email": true
    }
    ```
    """
    return await service.get_preferences(current_user)


@router.put("/preferences", summary="Update My Preferences")
async def update_preferences(
    request: UpdatePreferencesRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Update the doctor's preferences.

    **Access:** Doctor only

    **Request Body (all fields optional):**
    ```json
    {
      "language": "hi",
      "profile_visibility": "connections_only",
      "show_phone": true
    }
    ```

    **Response:**
    ```json
    { "message": "Preferences updated successfully" }
    ```

    **Allowed profile_visibility values:** `public`, `connections_only`, `private`
    """
    update_data = request.model_dump(exclude_unset=True)
    return await service.update_preferences(update_data, current_user)
