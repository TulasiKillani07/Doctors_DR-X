"""
Doctor Dashboard Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from app.core.auth import require_doctor
from app.api.v1.dashboard import service

router = APIRouter()


@router.get("/me", summary="Get My Dashboard")
async def get_my_dashboard(
    org_id: Optional[str] = Query(None, description="Organization ID — if provided, includes pharma data from MRX"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get the logged-in doctor's complete dashboard in one API call.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "doctor": {
        "name": "Dr. Mahesh Babu",
        "doctor_gid": "PRXDOC482915",
        "email": "mahesh@doctor.com",
        "phone": "9876543210",
        "avatar_url": "https://...",
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital",
        "qualification": "MBBS, MD"
      },
      "profile_completion": {
        "percentage": 85,
        "filled": 12,
        "total": 14,
        "missing_fields": ["license_number", "bio"]
      },
      "organizations": {
        "connected": 2,
        "list": [
          {
            "organization_id": "...",
            "organization_gid": "PRXORG482915",
            "organization_name": "Cipla",
            "logo": "https://...",
            "city": "Mumbai",
            "has_mrx": true,
            "joined_at": "2026-05-01T00:00:00"
          }
        ]
      },
      "activity_summary": {
        "total_cme": 5,
        "cme_attended": 3,
        "cme_upcoming": 2,
        "total_connections": 12,
        "pending_connection_requests": 3,
        "total_posts": 8,
        "unread_notifications": 5
      },
      "locations": {
        "total": 2,
        "active": 2,
        "primary": {
          "name": "Apollo Hospital - Jubilee Hills",
          "city": "Hyderabad",
          "type": "hospital"
        }
      },
      "suggested_doctors": [
        {
          "id": "...",
          "name": "Dr. Anil Kapoor",
          "doctor_gid": "PRXDOC123456",
          "specialization": "Cardiology",
          "avatar_url": null
        }
      ],
      "account": {
        "is_active": true,
        "is_email_verified": true,
        "is_phone_verified": false,
        "member_since": "2026-01-01T00:00:00",
        "last_login": "2026-07-21T10:00:00"
      }
    }
    ```

    **Sections:**
    - `doctor` — basic identity
    - `profile_completion` — percentage + missing fields
    - `organizations` — connected orgs with `has_mrx` flag
    - `activity_summary` — CME, connections, posts, notifications counts
    - `locations` — practice locations + primary
    - `suggested_doctors` — doctors to connect with (top 5)
    - `account` — verification and status
    """
    return await service.get_doctor_dashboard(current_user, org_id)
