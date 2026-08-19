"""
CME Routes — DRX Doctor Platform

DRX is the UI layer only. All CME data (events, registrations, attendance) is owned by MRX.
DRX forwards requests to MRX via mrx_client.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.core.auth import require_doctor
from app.api.v1.cme import service

router = APIRouter()
_bearer = HTTPBearer()


class CMERegisterRequest(BaseModel):
    event_id: str = Field(..., description="CME event ID from MRX")


@router.get("/organizations/{org_id}/events", summary="List CME Events (from MRX)")
async def list_org_events(
    org_id: str,
    status: Optional[str] = Query(None, description="upcoming, ongoing, completed"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor views CME events from a connected organization (fetched live from MRX).

    **Access:** Doctor only (must be connected to org)

    **Flow:** Doctor → Proxzar JWT → DRX → forwards same JWT → MRX /integration/cme → events

    **Response:**
    ```json
    {
      "total": 3,
      "events": [
        {
          "id": "6a605fe9f22a70a3c51b62c9",
          "title": "Cardiology Update 2026",
          "event_date": "2026-08-15",
          "event_time": "10:00 AM",
          "event_mode": "offline",
          "venue_name": "Taj Deccan Hotel",
          "speaker": "Dr. Ramesh Babu",
          "status": "upcoming"
        }
      ]
    }
    ```
    """
    return await service.list_org_cme_events(org_id, current_user["_id"], credentials.credentials, status, skip, limit)


@router.get("/organizations/{org_id}/events/{event_id}", summary="Get CME Event Detail")
async def get_event_detail(
    org_id: str,
    event_id: str,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor views full details of a single CME event. Tracks the view for admin analytics.

    **Access:** Doctor only (must be connected to org)

    **Response:**
    ```json
    {
      "id": "6a605fe9...",
      "title": "Cardiology Update 2026",
      "description": "Latest developments in cardiac care",
      "event_date": "2026-08-15",
      "event_time": "10:00 AM - 12:00 PM",
      "event_type": "Webinar",
      "event_mode": "online",
      "platform": "Zoom",
      "meeting_link": "https://zoom.us/j/...",
      "speaker": "Dr. Ramesh Babu",
      "max_attendees": 100,
      "status": "upcoming"
    }
    ```
    """
    return await service.get_cme_event_detail(org_id, event_id, current_user["_id"], credentials.credentials)


@router.post("/organizations/{org_id}/register", summary="Register for CME Event")
async def register_for_event(
    org_id: str,
    request: CMERegisterRequest,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor registers for a CME event. Registration is stored in MRX (MRX owns it).

    **Access:** Doctor only (must be connected to org)

    **Flow:** Doctor → Proxzar JWT → DRX validates → forwards to MRX → MRX stores registration

    **Request Body:**
    ```json
    { "event_id": "6a605fe9f22a70a3c51b62c9" }
    ```

    **Response:**
    ```json
    { "status": "registered", "registration_id": "...", "message": "Doctor registered for 'Cardiology Update 2026'" }
    ```

    **Validations (done by MRX):**
    - Event must exist
    - Cannot register twice
    - Event must have capacity
    """
    return await service.register_for_event(org_id, request.event_id, current_user, credentials.credentials)


@router.get("/organizations/{org_id}/my-registrations", summary="My CME Registrations")
async def get_my_cme(
    org_id: str,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor views their CME registrations for this organization (fetched from MRX).

    **Access:** Doctor only (must be connected to org)

    **Flow:** Doctor → Proxzar JWT → DRX → forwards same JWT → MRX /integration/cme/my-registrations → registrations

    **Response:**
    ```json
    {
      "total": 2,
      "registrations": [
        {
          "id": "...",
          "cme_id": "...",
          "event_title": "Cardiology Update 2026",
          "event_date": "2026-08-15",
          "event_time": "10:00 AM",
          "registration_status": "registered",
          "registered_at": "2026-07-22T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_my_cme(org_id, current_user, credentials.credentials)
