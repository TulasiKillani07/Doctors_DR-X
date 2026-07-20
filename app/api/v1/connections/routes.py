"""
Doctor Connections Routes — DRX Doctor Platform
Full doctor-to-doctor professional network
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from app.core.auth import require_doctor
from app.api.v1.connections import service

router = APIRouter()


@router.get("/discover", summary="Discover Doctors to Connect")
async def discover_doctors(
    search: Optional[str] = Query(None, description="Search by name"),
    specialization: Optional[str] = Query(None, description="Filter by specialization"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Discover doctors available to connect with. Excludes already connected, pending, and blocked users.

    **Access:** Doctor only

    **Request Body:** None (GET request)

    **Query Params:**
    - `search` — partial match on doctor name
    - `specialization` — filter by specialization
    - `page` / `limit` — pagination

    **Response:**
    ```json
    {
      "users": [
        {
          "user_id": "507f1f77bcf86cd799439011",
          "name": "Dr. Sneha Reddy",
          "doctor_gid": "PRXDOC123456",
          "specialization": "Neurology",
          "hospital": "Fortis Hospital",
          "avatar_url": null,
          "city": "Hyderabad"
        }
      ],
      "total": 50,
      "page": 1,
      "limit": 20,
      "total_pages": 3
    }
    ```
    """
    return await service.discover_users(current_user, search, specialization, page, limit)


@router.post("/request/{doctor_id}", summary="Send Connection Request")
async def send_request(doctor_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Send a connection request to another doctor.

    **Access:** Doctor only

    **Request Body:** None (doctor_id in URL path)

    **Response:**
    ```json
    {
      "connection_id": "507f1f77bcf86cd799439099",
      "receiver_name": "Dr. Sneha Reddy",
      "status": "pending",
      "message": "Connection request sent successfully"
    }
    ```

    **Errors:**
    - 400: Cannot connect to yourself / Already connected / Request pending / User blocked
    - 404: Doctor not found
    """
    return await service.send_connection_request(doctor_id, current_user)


@router.get("/requests/received", summary="Get Received Requests")
async def get_received(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** View pending connection requests sent TO you (waiting for your response).

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "requests": [
        {
          "connection_id": "...",
          "requester_id": "...",
          "requester_name": "Dr. Amit Patel",
          "requester_specialization": "Cardiology",
          "status": "pending",
          "created_at": "2026-07-14T10:00:00"
        }
      ],
      "total": 5,
      "page": 1,
      "limit": 20,
      "total_pages": 1
    }
    ```
    """
    return await service.get_received_requests(current_user, page, limit)


@router.get("/requests/sent", summary="Get Sent Requests")
async def get_sent(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** View pending connection requests you've sent (waiting for their response).

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "requests": [
        {
          "connection_id": "...",
          "receiver_id": "...",
          "receiver_name": "Dr. Priya Shah",
          "receiver_specialization": "Dermatology",
          "status": "pending",
          "created_at": "2026-07-13T08:00:00"
        }
      ],
      "total": 3,
      "page": 1,
      "limit": 20,
      "total_pages": 1
    }
    ```
    """
    return await service.get_sent_requests(current_user, page, limit)


@router.post("/requests/{connection_id}/accept", summary="Accept Connection Request")
async def accept(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Accept a pending connection request sent to you.

    **Access:** Doctor only (must be the receiver of the request)

    **Request Body:** None (connection_id in URL path)

    **Response:**
    ```json
    { "message": "Connection accepted", "connection_id": "..." }
    ```

    **Errors:**
    - 403: Only the receiver can accept
    - 400: Connection is not pending
    - 404: Connection not found
    """
    return await service.accept_connection(connection_id, current_user)


@router.post("/requests/{connection_id}/reject", summary="Reject Connection Request")
async def reject(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Reject a pending connection request sent to you.

    **Access:** Doctor only (must be the receiver)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Connection rejected" }
    ```

    **Errors:**
    - 403: Only the receiver can reject
    - 400: Connection is not pending
    """
    return await service.reject_connection(connection_id, current_user)


@router.delete("/requests/{connection_id}/cancel", summary="Cancel Sent Request")
async def cancel(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Cancel a connection request you previously sent (before the other person responds).

    **Access:** Doctor only (must be the requester)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Connection request cancelled" }
    ```

    **Errors:**
    - 403: Only the requester can cancel
    - 400: Can only cancel pending requests
    """
    return await service.cancel_request(connection_id, current_user)


@router.get("", summary="Get My Connections")
async def get_connections(
    status: Optional[str] = Query("accepted", description="Filter: accepted, blocked, or pending"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get your connections filtered by status.

    **Access:** Doctor only

    **Request Body:** None

    **Query Params:**
    - `status` — `accepted` (default), `blocked`, or `pending`
    - `page` / `limit` — pagination

    **Response:**
    ```json
    {
      "connections": [
        {
          "connection_id": "...",
          "user_id": "...",
          "name": "Dr. Sneha Reddy",
          "doctor_gid": "PRXDOC123456",
          "specialization": "Neurology",
          "hospital": "Fortis Hospital",
          "avatar_url": null,
          "connected_at": "2026-07-10T11:00:00"
        }
      ],
      "total": 25,
      "page": 1,
      "limit": 20,
      "total_pages": 2
    }
    ```
    """
    return await service.get_my_connections(current_user, status, page, limit)


@router.delete("/{connection_id}", summary="Remove Connection")
async def remove_connection(connection_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove/unfriend an established connection. Permanently deletes the connection.

    **Access:** Doctor only (must be part of the connection)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Connection removed successfully" }
    ```

    **Errors:**
    - 403: Not your connection
    - 400: Connection is not established (not accepted)
    """
    return await service.remove_connection(connection_id, current_user)


@router.post("/{doctor_id}/block", summary="Block Doctor")
async def block(doctor_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Block a doctor. Prevents them from sending connection requests. If already connected, connection becomes blocked.

    **Access:** Doctor only

    **Request Body:** None (doctor_id in URL path)

    **Response:**
    ```json
    { "message": "User blocked successfully" }
    ```

    **Errors:**
    - 400: Cannot block yourself
    - 404: Doctor not found
    """
    return await service.block_user(doctor_id, current_user)


@router.delete("/{doctor_id}/unblock", summary="Unblock Doctor")
async def unblock(doctor_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Unblock a previously blocked doctor. If they were connected before blocking, connection is restored.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    { "message": "User unblocked and connection restored" }
    ```
    or
    ```json
    { "message": "User unblocked successfully" }
    ```

    **Errors:**
    - 404: No blocked connection found with this user
    """
    return await service.unblock_user(doctor_id, current_user)
