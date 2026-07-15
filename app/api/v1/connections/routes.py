"""
Doctor Connections Routes — DRX Doctor Platform
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from app.core.auth import require_doctor
from app.api.v1.connections import service

router = APIRouter()


@router.post("/send/{doctor_id}", summary="Send Connection Request")
async def send_request(doctor_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Send a connection request to another doctor.

    **Access:** Doctor only

    **Response:** `{ "message": "Connection request sent" }`
    """
    return await service.send_connection_request(doctor_id, current_user)


@router.get("", summary="Get My Connections")
async def get_connections(
    status: Optional[str] = Query(None, description="Filter: pending, accepted, rejected"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get all connections (sent and received).

    **Access:** Doctor only

    **Query Params:** `status` — filter by connection status

    **Response:**
    ```json
    {
      "total": 5,
      "connections": [
        {
          "connection_id": "...",
          "status": "accepted",
          "direction": "sent",
          "doctor": {
            "id": "...",
            "name": "Dr. Sneha Reddy",
            "doctor_gid": "PRXDOC123456",
            "specialization": "Neurology",
            "hospital": "Fortis Hospital",
            "avatar_url": null
          },
          "created_at": "2026-07-01T00:00:00",
          "accepted_at": "2026-07-02T00:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_my_connections(current_user, status)


@router.get("/pending", summary="Get Pending Requests")
async def get_pending(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get incoming pending connection requests (waiting for your response).

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 2,
      "requests": [
        {
          "connection_id": "...",
          "doctor": { "id": "...", "name": "Dr. Amit", ... },
          "created_at": "2026-07-14T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_pending_requests(current_user)


@router.post("/{connection_id}/accept", summary="Accept Connection")
async def accept(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Accept a pending connection request.

    **Access:** Doctor only (must be the receiver)

    **Response:** `{ "message": "Connection accepted" }`
    """
    return await service.accept_connection(connection_id, current_user)


@router.post("/{connection_id}/reject", summary="Reject Connection")
async def reject(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Reject a pending connection request.

    **Access:** Doctor only (must be the receiver)

    **Response:** `{ "message": "Connection rejected" }`
    """
    return await service.reject_connection(connection_id, current_user)
