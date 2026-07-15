"""
Doctor Dashboard Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends
from typing import Dict
from app.core.auth import require_doctor
from app.api.v1.dashboard import service

router = APIRouter()


@router.get("/me", summary="Get My Dashboard")
async def get_my_dashboard(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get the logged-in doctor's dashboard with DRX-owned data.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "doctor": {
        "name": "Dr. Arjun Mehta",
        "doctor_gid": "PRXDOC482915",
        "email": "arjun@hospital.com",
        "avatar_url": "https://...",
        "specialization": "Cardiology",
        "hospital": "Apollo Hospital"
      },
      "profile_completion": {
        "percentage": 78,
        "filled": 11,
        "total": 14,
        "missing_fields": ["license_number", "bio", "avatar_url"]
      },
      "organizations": {
        "connected": 2,
        "list": [
          {
            "organization_id": "...",
            "organization_gid": "PRXORG482915",
            "organization_name": "XYZ Pharma Pvt Ltd",
            "logo": "https://...",
            "city": "Hyderabad",
            "joined_at": "2026-05-01T00:00:00"
          }
        ],
        "pending_invitations": 1
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
      "account": {
        "is_active": true,
        "is_email_verified": true,
        "is_phone_verified": false,
        "member_since": "2026-01-01T00:00:00",
        "last_login": "2026-07-15T10:00:00"
      }
    }
    ```

    **Sections:**
    - `doctor` — basic identity info
    - `profile_completion` — percentage + which fields are missing
    - `organizations` — connected pharma companies + pending invites
    - `locations` — practice locations summary with primary
    - `account` — verification and activity status

    **No MRX dependency.** All data comes from DRX collections only.
    Drugs, visits, CME will be added later after MRX integration is built.
    """
    return await service.get_doctor_dashboard(current_user)
