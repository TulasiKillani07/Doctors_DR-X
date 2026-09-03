"""
Doctor Profile Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends
from typing import Dict
from app.core.auth import get_current_user, require_doctor
from app.api.v1.profile.schemas import DoctorProfileResponse, DoctorProfileUpdateRequest
from app.api.v1.doctors.schemas import AddLocationRequest, UpdateLocationRequest, LocationListResponse, MessageResponse, SetLocationPriorityRequest
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
          "location_id": "b1f2c3d4-...",
          "location_priority": "PRIMARY",
          "facility_type": "HOSPITAL",
          "facility_type_other": null,
          "location_name": "Apollo Hospital - Jubilee Hills",
          "latitude": "17.4401",
          "longitude": "78.3489",
          "address": "Road 45, Jubilee Hills, Hyderabad",
          "area": "Jubilee Hills",
          "city": "Hyderabad",
          "district": "Hyderabad",
          "state": "Telangana",
          "country": "India",
          "postcode": "500033",
          "location_source": "MAP_SEARCH",
          "status": "ACTIVE"
        }
      ]
    }
    ```

    **Field reference:**
    - `location_id` — auto-generated unique ID (use it for update/delete/priority calls)
    - `location_priority` — PRIMARY / SECONDARY / OTHER
    - `facility_type` — HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER
    - `location_source` — CURRENT_LOCATION / MAP_SEARCH / MANUAL
    - `status` — ACTIVE / INACTIVE
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
      "location_priority": "SECONDARY",
      "facility_type": "CLINIC",
      "location_name": "My Clinic - Banjara Hills",
      "latitude": "17.4156",
      "longitude": "78.4347",
      "address": "Plot 23, Road No 12, Banjara Hills",
      "area": "Banjara Hills",
      "city": "Hyderabad",
      "district": "Hyderabad",
      "state": "Telangana",
      "country": "India",
      "postcode": "500034",
      "location_source": "MAP_SEARCH",
      "status": "ACTIVE"
    }
    ```

    **Required:** `location_priority`, `facility_type`, `location_name`, `city`, `district`, `state`, `country`, `postcode`

    **Optional:** `latitude`, `longitude`, `address`, `area`, `location_source`, `status`

    **Conditional:** `facility_type_other` — required only when `facility_type` = OTHER

    **Enums:**
    - `location_priority`: PRIMARY / SECONDARY / OTHER
    - `facility_type`: HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER
    - `location_source`: CURRENT_LOCATION / MAP_SEARCH / MANUAL
    - `status`: ACTIVE / INACTIVE

    **Note:** `location_id` is auto-generated server-side and returned in the response.

    **Response:**
    ```json
    { "message": "Location added successfully", "location_id": "b1f2c3d4-..." }
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
    **Purpose:** Doctor updates one of their own practice locations. Only the fields you send are changed.

    **Access:** Doctor only

    **Path Param:** `location_id` — the `location_id` returned by GET /profile/locations

    **Request Body (all fields optional — send only what changes):**
    ```json
    {
      "location_name": "My Clinic - New Name",
      "facility_type": "POLYCLINIC",
      "status": "INACTIVE"
    }
    ```

    **Updatable fields:** `location_name`, `facility_type`, `facility_type_other`, `address`, `area`,
    `city`, `district`, `state`, `country`, `postcode`, `latitude`, `longitude`, `location_source`,
    `status`, `location_priority`

    **Enums:**
    - `location_priority`: PRIMARY / SECONDARY / OTHER
    - `facility_type`: HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER
    - `location_source`: CURRENT_LOCATION / MAP_SEARCH / MANUAL
    - `status`: ACTIVE / INACTIVE

    **Note:** To change priority, prefer POST /profile/locations/{location_id}/priority
    (it enforces single-PRIMARY rules).

    **Response:**
    ```json
    { "message": "Location updated successfully" }
    ```

    **Errors:**
    - 404: Location not found
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

    **Path Param:** `location_id` — the `location_id` returned by GET /profile/locations

    **Response:**
    ```json
    { "message": "Location removed successfully" }
    ```

    **Errors:**
    - 404: Doctor or location not found
    """
    return await service.delete_my_location(location_id, current_user)


@router.post("/locations/{location_id}/priority", response_model=MessageResponse, summary="Set Location Priority")
async def set_location_priority(
    location_id: str,
    request: SetLocationPriorityRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Change a location's priority (PRIMARY / SECONDARY / OTHER).
    A doctor can re-assign priorities anytime — make a secondary the primary, etc.

    **Access:** Doctor only

    **Request Body:**
    ```json
    { "priority": "PRIMARY" }
    ```

    **Response:**
    ```json
    { "message": "Location priority set to PRIMARY" }
    ```

    **Rules:**
    - Only one location can be PRIMARY at a time
    - Setting a new PRIMARY demotes the previous PRIMARY to SECONDARY
    - Valid values: PRIMARY, SECONDARY, OTHER
    """
    return await service.set_location_priority(location_id, request.priority, current_user)
