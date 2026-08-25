"""
Doctor Requests Routes — DRX Doctor Platform

Flow:
  MRX Admin → POST /integration/doctor-requests → PENDING_DOCTOR
  Doctor → POST /doctor-requests/{id}/accept → PENDING_ADMIN
  Doctor → POST /doctor-requests/{id}/reject → REJECTED_BY_DOCTOR
  DRX Admin → POST /doctor-requests/{id}/approve → APPROVED (link + MRX sync)
  DRX Admin → POST /doctor-requests/{id}/reject → REJECTED_BY_ADMIN
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
from pydantic import BaseModel, Field
from app.core.auth import require_doctor, require_platform_admin
from app.core.proxzar_auth import require_proxzar_auth
from fastapi import HTTPException, status
from app.api.v1.doctor_requests import service

router = APIRouter()
_bearer = HTTPBearer()


# ── Schemas ──

class CreateDoctorRequestBody(BaseModel):
    username: str = Field(..., description="Doctor's username (global identity)")
    organization_gid: str = Field(..., description="Organization GID (e.g. PRXORG631774)")


# ══════════════════════════════════════════════════════════════
# MRX Admin — Create request (Proxzar JWT, role=ADMIN)
# ══════════════════════════════════════════════════════════════

@router.post("/integration/doctor-requests", status_code=201, summary="Request Doctor to Join Org (MRX Admin)")
async def create_doctor_request(
    body: CreateDoctorRequestBody,
    proxzar_identity: dict = Depends(require_proxzar_auth)
):
    """
    **Purpose:** MRX Admin requests a doctor to join their organization.

    **Access:** Proxzar JWT with role = ADMIN

    **Request Body:**
    ```json
    {
      "username": "rahul_mehta",
      "organization_gid": "PRXORG631774"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Request sent to doctor",
      "request_id": "...",
      "status": "PENDING"
    }
    ```

    **Flow:** Doctor receives notification → accepts/rejects → if accepted, DRX admin approves/rejects.
    """
    if proxzar_identity.get("role") != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN role required")

    requested_by = proxzar_identity.get("sub", "unknown")
    return await service.create_request(body.username, body.organization_gid, requested_by)


@router.get("/integration/doctor-requests", summary="View Sent Requests (MRX Admin)")
async def get_org_doctor_requests(
    organization_gid: str,
    proxzar_identity: dict = Depends(require_proxzar_auth)
):
    """
    **Purpose:** MRX Admin views all doctor requests they sent for their organization.

    **Access:** Proxzar JWT with role = ADMIN

    **Query Params:** `organization_gid` (required)

    **Response:**
    ```json
    {
      "total": 3,
      "requests": [
        {
          "id": "...",
          "doctor_gid": "PRXDOC485235",
          "doctor_username": "rahul_mehta",
          "organization_gid": "PRXORG631774",
          "organization_name": "Sanofi",
          "requested_by": "tulasi",
          "status": "PENDING",
          "doctor_accepted": null,
          "admin_accepted": null,
          "rejected_by": null,
          "created_at": "..."
        }
      ]
    }
    ```

    **Statuses:**
    - `PENDING` — waiting for doctor or admin action
    - `APPROVED` — doctor and admin both accepted, doctor linked
    - `REJECTED` — rejected by doctor or admin (check `rejected_by` field)
    """
    if proxzar_identity.get("role") != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN role required")

    return await service.get_requests_by_org(organization_gid)


# ══════════════════════════════════════════════════════════════
# Doctor — View and respond to requests
# ══════════════════════════════════════════════════════════════

@router.get("/doctor-requests/pending", summary="My Pending Requests (Doctor)")
async def get_my_pending_requests(
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor views pending organization requests.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 1,
      "requests": [
        {
          "id": "...",
          "doctor_gid": "PRXDOC485235",
          "organization_id": "...",
          "organization_name": "Sanofi",
          "requested_by": "tulasi",
          "status": "PENDING_DOCTOR",
          "created_at": "2026-08-19T..."
        }
      ]
    }
    ```
    """
    return await service.get_doctor_pending_requests(current_user["_id"])


@router.post("/doctor-requests/{request_id}/accept", summary="Accept Request (Doctor)")
async def doctor_accept_request(
    request_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor accepts the organization's request.

    **Access:** Doctor only (must be the requested doctor)

    **Response:**
    ```json
    {
      "message": "Request accepted. Awaiting DRX admin approval.",
      "status": "PENDING_ADMIN"
    }
    ```
    """
    return await service.doctor_accept(request_id, current_user["_id"])


@router.post("/doctor-requests/{request_id}/reject", summary="Reject Request (Doctor)")
async def doctor_reject_request(
    request_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor rejects the organization's request.

    **Access:** Doctor only (must be the requested doctor)

    **Response:**
    ```json
    {
      "message": "Request rejected.",
      "status": "REJECTED_BY_DOCTOR"
    }
    ```
    """
    return await service.doctor_reject(request_id, current_user["_id"])


# ══════════════════════════════════════════════════════════════
# DRX Admin — View and approve/reject requests
# ══════════════════════════════════════════════════════════════

@router.get("/doctor-requests/pending-approval", summary="Requests Awaiting Approval (Admin)")
async def get_pending_approval_requests(
    current_user: Dict = Depends(require_platform_admin)
):
    """
    **Purpose:** DRX Admin views requests that doctors have accepted and need admin approval.

    **Access:** Platform Admin only

    **Response:**
    ```json
    {
      "total": 1,
      "requests": [
        {
          "id": "...",
          "doctor_gid": "PRXDOC485235",
          "doctor_id": "...",
          "organization_id": "...",
          "organization_name": "Sanofi",
          "requested_by": "tulasi",
          "status": "PENDING_ADMIN",
          "created_at": "...",
          "doctor_responded_at": "..."
        }
      ]
    }
    ```
    """
    return await service.get_admin_pending_requests()


@router.post("/doctor-requests/{request_id}/approve", summary="Approve Request (Admin)")
async def admin_approve_request(
    request_id: str,
    current_user: Dict = Depends(require_platform_admin),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** DRX Admin approves the request. This:
    1. Creates ACTIVE doctor-organization relationship
    2. Syncs doctor to the org's MRX backend

    **Access:** Platform Admin only

    **Response:**
    ```json
    {
      "message": "Request approved. Doctor linked to organization.",
      "status": "APPROVED"
    }
    ```
    """
    admin_username = current_user.get("username", "admin")
    return await service.admin_approve(request_id, admin_username, credentials.credentials)


@router.post("/doctor-requests/{request_id}/admin-reject", summary="Reject Request (Admin)")
async def admin_reject_request(
    request_id: str,
    current_user: Dict = Depends(require_platform_admin)
):
    """
    **Purpose:** DRX Admin rejects the request after doctor accepted.

    **Access:** Platform Admin only

    **Response:**
    ```json
    {
      "message": "Request rejected.",
      "status": "REJECTED_BY_ADMIN"
    }
    ```
    """
    admin_username = current_user.get("username", "admin")
    return await service.admin_reject(request_id, admin_username)
