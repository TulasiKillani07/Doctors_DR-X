"""
Doctor-Organization Relationship Routes — Platform Admin only
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.core.auth import require_platform_admin
from app.api.v1.doctor_organizations import service
from app.api.v1.doctor_organizations.schemas import (
    CreateRelationshipRequest, UpdateStatusRequest,
    DoctorOrganizationResponse, DoctorOrganizationListResponse, MessageResponse
)

router = APIRouter()


@router.post("", response_model=MessageResponse, status_code=201, summary="Create Relationship")
async def create_relationship(
    request: CreateRelationshipRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Create a new doctor-organization relationship. Starts as PENDING.

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "doctor_id": "507f1f77bcf86cd799439011",
      "organization_id": "507f1f77bcf86cd799439021"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Relationship created (PENDING)",
      "relationship_id": "507f1f77bcf86cd799439031"
    }
    ```

    **Validations:**
    - Doctor must exist
    - Organization must exist
    - No duplicate relationship (doctor_id + organization_id must be unique)
    """
    return await service.create_relationship(
        request.doctor_id, request.organization_id, current_user
    )


@router.get("", response_model=DoctorOrganizationListResponse, summary="List Relationships")
async def list_relationships(
    doctor_id: Optional[str] = Query(None, description="Filter by doctor ID"),
    organization_id: Optional[str] = Query(None, description="Filter by organization ID"),
    status: Optional[str] = Query(None, description="Filter by status: PENDING, ACTIVE, REJECTED, REMOVED"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** List doctor-organization relationships with filters.

    **Access:** Platform Admin only

    **Query Parameters:**
    - `doctor_id` — filter by specific doctor
    - `organization_id` — filter by specific organization
    - `status` — PENDING, ACTIVE, REJECTED, REMOVED
    - `skip` / `limit` — pagination

    **Response:**
    ```json
    {
      "total": 10,
      "relationships": [
        {
          "id": "...",
          "doctor_id": "...",
          "organization_id": "...",
          "status": "PENDING",
          "requested_by": "...",
          "requested_at": "2026-07-09T10:00:00",
          "responded_at": null,
          "joined_at": null,
          "removed_at": null
        }
      ]
    }
    ```
    """
    return await service.list_relationships(doctor_id, organization_id, status, skip, limit)


@router.get("/{rel_id}", response_model=DoctorOrganizationResponse, summary="Get Relationship")
async def get_relationship(
    rel_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Get a single relationship by ID.

    **Access:** Platform Admin only

    **Response:** Full relationship document with all timestamps.
    """
    return await service.get_relationship(rel_id)


@router.put("/{rel_id}/status", response_model=MessageResponse, summary="Update Relationship Status")
async def update_status(
    rel_id: str,
    request: UpdateStatusRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Change relationship status (admin override).

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    { "status": "ACTIVE" }
    ```

    **Valid statuses:** ACTIVE, REJECTED, REMOVED

    **Side effects:**
    - `ACTIVE` → sets `responded_at` and `joined_at`
    - `REJECTED` → sets `responded_at`
    - `REMOVED` → sets `removed_at`

    **Response:**
    ```json
    { "message": "Relationship status updated to ACTIVE" }
    ```
    """
    return await service.update_status(rel_id, request.status)
