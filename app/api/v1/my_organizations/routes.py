"""
My Organizations Routes — DRX Doctor Platform
Doctor views and manages their organization memberships
"""

from fastapi import APIRouter, Depends
from typing import Dict
from app.core.auth import require_doctor
from app.api.v1.my_organizations import service

router = APIRouter()


@router.get("", summary="List My Organizations")
async def get_my_organizations(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get all organizations the doctor is connected to (ACTIVE memberships).

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 2,
      "organizations": [
        {
          "organization_id": "507f1f77bcf86cd799439011",
          "organization_gid": "PRXORG482915",
          "organization_name": "XYZ Pharma Pvt Ltd",
          "logo": "https://cdn.example.com/xyz-logo.png",
          "contact_email": "info@xyzpharma.com",
          "city": "Hyderabad",
          "state": "Telangana",
          "country": "India",
          "org_status": "ACTIVE",
          "joined_at": "2026-05-01T00:00:00",
          "relationship_status": "ACTIVE"
        },
        {
          "organization_id": "...",
          "organization_gid": "PRXORG123456",
          "organization_name": "Sun Pharma",
          "logo": null,
          "city": "Mumbai",
          "state": "Maharashtra",
          "country": "India",
          "org_status": "ACTIVE",
          "joined_at": "2026-06-15T00:00:00",
          "relationship_status": "ACTIVE"
        }
      ]
    }
    ```
    """
    return await service.get_my_organizations(current_user)


@router.get("/invitations", summary="Get Pending Organization Invitations")
async def get_invitations(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get pending organization invitations waiting for the doctor's response.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 1,
      "invitations": [
        {
          "relationship_id": "507f1f77bcf86cd799439099",
          "organization_id": "...",
          "organization_gid": "PRXORG789012",
          "organization_name": "Cipla Ltd",
          "logo": "https://cdn.example.com/cipla-logo.png",
          "city": "Mumbai",
          "requested_at": "2026-07-10T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_pending_invitations(current_user)


@router.post("/invitations/{relationship_id}/accept", summary="Accept Organization Invitation")
async def accept_invitation(
    relationship_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Accept an organization's invitation to join their network. Doctor becomes part of the org.

    **Access:** Doctor only (must be the invited doctor)

    **Request Body:** None (relationship_id in URL path)

    **Response:**
    ```json
    { "message": "Invitation accepted. You are now connected to this organization." }
    ```

    **What happens after acceptance:**
    - Relationship status changes: PENDING → ACTIVE
    - Doctor can now view org's drugs, CME events
    - Organization appears in "My Organizations" list

    **Errors:**
    - 400: Invitation already responded to
    - 403: Not your invitation
    - 404: Invitation not found
    """
    return await service.respond_to_invitation(relationship_id, "accept", current_user)


@router.post("/invitations/{relationship_id}/reject", summary="Reject Organization Invitation")
async def reject_invitation(
    relationship_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Reject an organization's invitation.

    **Access:** Doctor only (must be the invited doctor)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Invitation rejected." }
    ```

    **Errors:**
    - 400: Invitation already responded to
    - 403: Not your invitation
    """
    return await service.respond_to_invitation(relationship_id, "reject", current_user)
