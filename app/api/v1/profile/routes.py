"""
Doctor Profile Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends
from typing import Dict
from app.core.auth import get_current_user, require_doctor
from app.api.v1.profile.schemas import DoctorProfileResponse, DoctorProfileUpdateRequest
from app.api.v1.doctors.schemas import AddLocationRequest, UpdateLocationRequest, LocationListResponse, MessageResponse
from app.api.v1.profile import service

router = APIRouter()


@router.get("/me", response_model=DoctorProfileResponse, summary="Get My Profile")
async def get_my_profile(current_user: Dict = Depends(get_current_user)):
    """
    **Purpose:** Get the currently logged-in user's complete profile.

    **Access:** Doctor, Platform Admin

    **Request Body:** None

    **Response (Doctor):**
    ```json
    {
      "user_id": "507f1f77bcf86cd799439011",
      "doctor_gid": "PRXDOC482915",
      "email": "arjun@doctor.com",
      "phone": "9876543210",
      "name": "Dr. Arjun Mehta",
      "role": "DOCTOR",
      "specialization": "Cardiology",
      "hospital": "Apollo Hospital",
      "license_number": "MH12345",
      "experience_years": 10.5,
      "qualification": "MBBS, MD Cardiology",
      "bio": "Senior Cardiologist with 10 years experience",
      "avatar_url": "https://...",
      "location": "Mumbai, Maharashtra",
      "city": "Mumbai",
      "state": "Maharashtra",
      "country": "India",
      "is_active": true,
      "is_email_verified": true,
      "is_phone_verified": false,
      "created_at": "2026-01-01T00:00:00",
      "updated_at": "2026-07-14T10:00:00"
    }
    ```
    """
    return await service.get_my_profile(current_user)


@router.put("/me", summary="Update My Profile")
async def update_my_profile(
    profile_data: DoctorProfileUpdateRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Update the currently logged-in doctor's profile.

    **Access:** Doctor only

    **Request Body (all fields optional — send only what you want to update):**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "phone": "9876543210",
      "specialization": "Cardiology",
      "hospital": "Apollo Hospital",
      "license_number": "MH12345",
      "experience_years": 10.5,
      "qualification": "MBBS, MD Cardiology",
      "bio": "Senior Cardiologist",
      "avatar_url": "https://...",
      "location": "Mumbai, Maharashtra",
      "city": "Mumbai",
      "state": "Maharashtra",
      "country": "India"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Profile updated successfully"
    }
    ```

    **Rules:**
    - All fields are optional (partial update)
    - Cannot update: email, doctor_gid (immutable)
    - Only doctors can use this endpoint
    """
    update_data = profile_data.model_dump(exclude_unset=True)
    return await service.update_my_profile(update_data, current_user)


# ══════════════════════════════════════════════════════════════
# Doctor Location Self-Service
# ══════════════════════════════════════════════════════════════

@router.get("/locations", response_model=LocationListResponse, summary="Get My Locations")
async def get_my_locations(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get the logged-in doctor's practice locations.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 2,
      "locations": [
        {
          "id": "a1b2c3d4",
          "type": "hospital",
          "name": "Apollo Hospital - Jubilee Hills",
          "address": "Road 45, Jubilee Hills, Hyderabad",
          "country": "India",
          "state": "Telangana",
          "district": "Ranga Reddy",
          "city": "Hyderabad",
          "area": "Jubilee Hills",
          "latitude": 17.4401,
          "longitude": 78.3489,
          "is_active": true,
          "geofence_radius": 100,
          "is_primary": true,
          "added_by": "self",
          "added_at": "2026-07-15T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_my_locations(current_user)


@router.post("/locations", status_code=201, summary="Add My Location")
async def add_my_location(
    request: AddLocationRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor adds a new practice location to their own profile.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "name": "My Clinic - Banjara Hills",
      "address": "Plot 23, Road No 12, Banjara Hills",
      "country": "India",
      "state": "Telangana",
      "district": "Hyderabad",
      "city": "Hyderabad",
      "area": "Banjara Hills",
      "latitude": 17.4156,
      "longitude": 78.4347,
      "type": "solo_clinic",
      "geofence_radius": 50
    }
    ```

    **Response:**
    ```json
    { "message": "Location added successfully" }
    ```
    """
    return await service.add_my_location(request.model_dump(), current_user)


@router.put("/locations/{location_id}", response_model=MessageResponse, summary="Update My Location")
async def update_my_location(
    location_id: str,
    request: UpdateLocationRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor updates one of their own practice locations.

    **Access:** Doctor only

    **Request Body (all fields optional):**
    ```json
    {
      "name": "My Clinic - New Name",
      "is_active": false
    }
    ```

    **Response:**
    ```json
    { "message": "Location updated successfully" }
    ```
    """
    update_data = request.model_dump(exclude_unset=True)
    return await service.update_my_location(location_id, update_data, current_user)


@router.delete("/locations/{location_id}", response_model=MessageResponse, summary="Delete My Location")
async def delete_my_location(
    location_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor removes a practice location from their profile.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Location removed successfully" }
    ```
    """
    return await service.delete_my_location(location_id, current_user)


@router.post("/locations/{location_id}/set-primary", response_model=MessageResponse, summary="Set Primary Location")
async def set_primary_location(
    location_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Set a location as the doctor's primary practice location.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Primary location updated" }
    ```

    **Rules:**
    - Only one location can be primary at a time
    - Setting a new primary automatically unsets the previous one
    """
    return await service.set_primary_location(location_id, current_user)
