"""
Doctor Management Routes — Platform Admin only
"""

from fastapi import APIRouter, Depends, UploadFile, File, Query
from typing import Optional
from app.core.auth import require_platform_admin
from app.api.v1.doctors import service
from app.api.v1.doctors.schemas import (
    BulkUploadResponse, DoctorDetailResponse, DoctorUpdateByAdminRequest,
    DoctorListResponse, AddLocationRequest, UpdateLocationRequest,
    LocationListResponse, MessageResponse, SPECIALIZATIONS,
    AddDoctorRequest, AddDoctorResponse
)

router = APIRouter()


@router.get("/specializations", summary="Get Specialization Options")
async def get_specializations():
    """
    **Purpose:** Get the list of valid doctor specialization options for dropdown.

    **Access:** Public (no auth required)

    **Response:**
    ```json
    { "specializations": ["General Physician", "Cardiology", ...], "total": 57 }
    ```
    """
    return {"specializations": SPECIALIZATIONS, "total": len(SPECIALIZATIONS)}


@router.post("", response_model=AddDoctorResponse, status_code=201, summary="Add Doctor")
async def add_doctor(
    request: AddDoctorRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Platform admin manually adds a single doctor.

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "username": "arjun_mehta",
      "email": "arjun@hospital.com",
      "phone": "9876543210",
      "password": "Doctor@123",
      "specialization": "Cardiology",
      "qualification": "MBBS, MD Cardiology",
      "license_number": "MH12345",
      "location": {
        "location_priority": "PRIMARY",
        "facility_type": "HOSPITAL",
        "location_name": "Apollo Hospital",
        "latitude": "17.4401",
        "longitude": "78.3489",
        "address": "Road 45, Jubilee Hills",
        "area": "Jubilee Hills",
        "city": "Hyderabad",
        "district": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "postcode": "500033",
        "location_source": "MAP_SEARCH",
        "status": "ACTIVE"
      }
    }
    ```

    **Doctor required:** `name`, `username`, `email`, `phone`, `password`

    **Doctor optional:** `specialization`, `qualification`, `license_number`, `location`

    **Location required (if location provided):** `location_priority`, `facility_type`, `location_name`, `city`, `district`, `state`, `country`, `postcode`

    **Location optional:** `latitude`, `longitude`, `address`, `area`, `location_source`, `status`

    **Location conditional:** `facility_type_other` — required only when `facility_type` = OTHER

    **Enums:**
    - `location_priority`: PRIMARY / SECONDARY / OTHER
    - `facility_type`: HOSPITAL / CLINIC / POLYCLINIC / MEDICAL_CENTER / INSTITUTION_OR_MEDICAL_COLLEGE / OTHER
    - `location_source`: CURRENT_LOCATION / MAP_SEARCH / MANUAL

    **Response:**
    ```json
    {
      "message": "Doctor added successfully",
      "doctor_id": "6a6aef18...",
      "doctor_gid": "PRXDOC482915"
    }
    ```

    **Rules:**
    - Email, phone, and username must be unique
    - Username: 3-30 chars, lowercase letters, numbers, underscores only
    - Password: 8-64 chars, must include uppercase, lowercase, number, and symbol
    - Doctor authenticates via Proxzar OAuth using their username
    - Specialization must be from predefined list (GET /doctors/specializations)
    - `location_id` is auto-generated server-side
    """
    return await service.add_single_doctor(request.model_dump())
# ══════════════════════════════════════════════════════════════
# Doctor CRUD
# ══════════════════════════════════════════════════════════════

@router.get("", response_model=DoctorListResponse, summary="List All Doctors")
async def list_doctors(
    search: Optional[str] = Query(None, description="Search by name, email, GID, specialization"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** List all doctors on the platform with search and pagination.

    **Access:** Platform Admin only

    **Query Params:** `search`, `skip`, `limit`

    **Response:**
    ```json
    {
      "total": 150,
      "doctors": [
        {
          "id": "...",
          "doctor_gid": "PRXDOC482915",
          "name": "Dr. Arjun Mehta",
          "email": "arjun@hospital.com",
          "phone": "9876543210",
          "specialization": "Cardiology",
          "hospital": "Apollo Hospital",
          "city": "Mumbai",
          "state": "Maharashtra",
          "is_active": true,
          "created_at": "2026-01-01T00:00:00"
        }
      ]
    }
    ```
    """
    return await service.list_all_doctors(search=search, skip=skip, limit=limit)


@router.get("/{doctor_id}", response_model=DoctorDetailResponse, summary="Get Doctor Detail")
async def get_doctor(
    doctor_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Get a single doctor's full profile including locations.

    **Access:** Platform Admin only

    **Response:**
    ```json
    {
      "id": "...",
      "doctor_gid": "PRXDOC482915",
      "email": "arjun@hospital.com",
      "phone": "9876543210",
      "name": "Dr. Arjun Mehta",
      "specialization": "Cardiology",
      "hospital": "Apollo Hospital",
      "qualification": "MBBS, MD",
      "experience_years": 10.5,
      "bio": "Senior Cardiologist",
      "avatar_url": "https://...",
      "city": "Mumbai",
      "state": "Maharashtra",
      "country": "India",
      "locations": [...],
      "is_active": true
    }
    ```
    """
    return await service.get_doctor_by_id(doctor_id)


@router.put("/{doctor_id}", response_model=MessageResponse, summary="Update Doctor (Admin)")
async def update_doctor(
    doctor_id: str,
    request: DoctorUpdateByAdminRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Admin updates a doctor's profile information.

    **Access:** Platform Admin only

    **Request Body (all fields optional — send only what you want to update):**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "specialization": "Interventional Cardiology",
      "hospital": "Apollo Hospital - New Wing",
      "is_active": false
    }
    ```

    **Response:**
    ```json
    { "message": "Doctor updated successfully" }
    ```
    """
    update_data = request.model_dump(exclude_unset=True)
    return await service.update_doctor_by_admin(doctor_id, update_data)


@router.post("/bulk-upload", response_model=BulkUploadResponse, summary="Bulk Upload Doctors")
async def bulk_upload_doctors(
    file: UploadFile = File(..., description="CSV or Excel file"),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Bulk register doctors from CSV/Excel file.

    **Access:** Platform Admin only

    **Required Columns:** name, email, phone

    **Response:**
    ```json
    {
      "total_rows": 20,
      "successful": 18,
      "failed": 2,
      "errors": [...],
      "message": "Bulk upload completed. 18 doctors added, 2 rows failed."
    }
    ```
    """
    return await service.bulk_upload_doctors(file, current_user)


# ══════════════════════════════════════════════════════════════
# Location Management
# ══════════════════════════════════════════════════════════════

@router.get("/{doctor_id}/locations", response_model=LocationListResponse, summary="Get Doctor Locations")
async def get_locations(
    doctor_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Get all practice locations for a doctor.

    **Access:** Platform Admin only

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
    """
    return await service.get_doctor_locations(doctor_id)


@router.post("/{doctor_id}/locations", response_model=MessageResponse, status_code=201, summary="Add Doctor Location")
async def add_location(
    doctor_id: str,
    request: AddLocationRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Add a new practice location to a doctor's profile.

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "location_priority": "PRIMARY",
      "facility_type": "HOSPITAL",
      "location_name": "Apollo Hospital - Jubilee Hills",
      "latitude": "17.4401",
      "longitude": "78.3489",
      "address": "Road 45, Jubilee Hills, Hyderabad - 500033",
      "area": "Jubilee Hills",
      "city": "Hyderabad",
      "district": "Hyderabad",
      "state": "Telangana",
      "country": "India",
      "postcode": "500033",
      "location_source": "MANUAL",
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

    **Response:**
    ```json
    { "message": "Location added successfully", "location_id": "b1f2c3d4-..." }
    ```
    """
    return await service.add_doctor_location(doctor_id, request.model_dump(), current_user)


@router.put("/{doctor_id}/locations/{location_id}", response_model=MessageResponse, summary="Update Location")
async def update_location(
    doctor_id: str,
    location_id: str,
    request: UpdateLocationRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Update an existing practice location.

    **Access:** Platform Admin only

    **Request Body (all fields optional):**
    ```json
    {
      "location_name": "Apollo Hospital - New Wing",
      "facility_type": "MEDICAL_CENTER",
      "status": "INACTIVE"
    }
    ```

    **Path Param:** `location_id` — the `location_id` from GET /doctors/{doctor_id}/locations

    **Updatable fields:** `location_name`, `facility_type`, `facility_type_other`, `address`, `area`,
    `city`, `district`, `state`, `country`, `postcode`, `latitude`, `longitude`, `location_source`,
    `status`, `location_priority`

    **Response:**
    ```json
    { "message": "Location updated successfully" }
    ```
    """
    update_data = request.model_dump(exclude_unset=True)
    return await service.update_doctor_location(doctor_id, location_id, update_data)


@router.delete("/{doctor_id}/locations/{location_id}", response_model=MessageResponse, summary="Delete Location")
async def delete_location(
    doctor_id: str,
    location_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Remove a practice location from a doctor.

    **Access:** Platform Admin only

    **Path Param:** `location_id` — the `location_id` from GET /doctors/{doctor_id}/locations

    **Response:**
    ```json
    { "message": "Location removed successfully" }
    ```
    """
    return await service.delete_doctor_location(doctor_id, location_id)
