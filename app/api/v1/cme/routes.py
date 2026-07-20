"""
CME Routes — DRX Doctor Platform

DRX owns: registrations, my CME, attendance
MRX owns: event creation and event data (fetched via mrx_client)
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.core.auth import require_doctor, require_platform_admin
from app.api.v1.cme import service

router = APIRouter()


class CMERegisterRequest(BaseModel):
    event_id: Optional[str] = Field(None, description="Event reference ID from MRX (for tracking)")
    event_title: str = Field(..., min_length=2, max_length=300)
    event_date: Optional[str] = Field(None, description="Event date (ISO format)")


class MarkAttendanceRequest(BaseModel):
    attended: bool = Field(..., description="True = attended, False = absent")


# ══════════════════════════════════════════════════════════════
# Doctor-facing endpoints
# ══════════════════════════════════════════════════════════════

@router.get("/organizations/{org_id}/events", summary="List CME Events (from MRX)")
async def list_org_events(
    org_id: str,
    status: Optional[str] = Query(None, description="UPCOMING, ONGOING, COMPLETED"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor views CME events from a connected organization (fetched live from MRX).

    **Access:** Doctor only (must be connected to org)

    **Flow:**
    ```
    Doctor → DRX → mrx_client → MRX /integration/cme → events
    ```

    **Response:**
    ```json
    {
      "total": 3,
      "events": [
        {
          "title": "Cardiology Update 2026",
          "event_date": "2026-08-15",
          "venue": "Taj Hotel",
          "city": "Mumbai",
          "specialization": "Cardiology",
          "status": "UPCOMING",
          "max_participants": 100,
          "registered_count": 45
        }
      ],
      "organization": "XYZ Pharma"
    }
    ```
    """
    return await service.list_org_cme_events(org_id, current_user["_id"], status, skip, limit)


@router.post("/organizations/{org_id}/register", summary="Register for CME Event")
async def register_for_event(
    org_id: str,
    request: CMERegisterRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor registers for a CME event. Registration stored in DRX.

    **Access:** Doctor only (must be connected to org)

    **Request Body:**
    ```json
    {
      "event_id": "mrx_event_id_123",
      "event_title": "Cardiology Update 2026",
      "event_date": "2026-08-15"
    }
    ```

    **Response:**
    ```json
    { "message": "Successfully registered for 'Cardiology Update 2026'" }
    ```

    **Rules:**
    - Cannot register twice for the same event
    - Must be connected to the organization
    """
    return await service.register_for_event(
        org_id, request.model_dump(), current_user["_id"], current_user.get("name", "")
    )


@router.get("/my-cme", summary="Get My CME Registrations")
async def get_my_cme(
    status: Optional[str] = Query(None, description="REGISTERED, ATTENDED, ABSENT, CANCELLED"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor views all their CME registrations across all organizations.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 5,
      "registrations": [
        {
          "id": "...",
          "organization_id": "...",
          "event_id": "mrx_event_123",
          "event_title": "Cardiology Update 2026",
          "event_date": "2026-08-15",
          "status": "REGISTERED",
          "registered_at": "2026-07-15T10:00:00",
          "attended_at": null
        }
      ]
    }
    ```
    """
    return await service.get_my_cme(current_user["_id"], status)


@router.post("/registrations/{registration_id}/cancel", summary="Cancel CME Registration")
async def cancel_registration(
    registration_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor cancels their CME registration.

    **Access:** Doctor only (own registration)

    **Response:**
    ```json
    { "message": "Registration cancelled" }
    ```

    **Rules:**
    - Can only cancel if status is REGISTERED
    - Cannot cancel ATTENDED or ABSENT
    """
    return await service.cancel_registration(registration_id, current_user["_id"])


# ══════════════════════════════════════════════════════════════
# Admin-facing endpoints (attendance management)
# ══════════════════════════════════════════════════════════════

@router.post("/registrations/{registration_id}/attendance", summary="Mark Attendance (Admin)")
async def mark_attendance(
    registration_id: str,
    request: MarkAttendanceRequest,
    current_user: Dict = Depends(require_platform_admin)
):
    """
    **Purpose:** Platform admin marks attendance for a CME registration.

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    { "attended": true }
    ```

    **Response:**
    ```json
    { "message": "Attendance marked: ATTENDED" }
    ```
    """
    return await service.mark_attendance(registration_id, request.attended, current_user)
