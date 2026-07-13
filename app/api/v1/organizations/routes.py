"""
Organization Management Routes — Platform Admin only
"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.core.auth import require_platform_admin
from app.api.v1.organizations import service
from app.api.v1.organizations.schemas import (
    OrganizationCreateRequest, OrganizationUpdateRequest,
    OrganizationResponse, OrganizationListResponse, MessageResponse
)

router = APIRouter()


@router.post("", response_model=MessageResponse, status_code=201, summary="Create Organization")
async def create_organization(
    request: OrganizationCreateRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Register a new pharmaceutical company on the platform.

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "organization_name": "XYZ Pharma Pvt Ltd",
      "contact_email": "info@xyzpharma.com",
      "contact_phone": "9876543210",
      "org_admin": "Rajesh Kumar",
      "admin_email": "rajesh@xyzpharma.com",
      "admin_phone": "9876543211",
      "address": "Plot 45, Industrial Area",
      "city": "Hyderabad",
      "state": "Telangana",
      "country": "India",
      "pincode": "500032"
    }
    ```

    **Response:**
    ```json
    {
      "message": "Organization created successfully",
      "organization_id": "507f1f77bcf86cd799439011",
      "organization_gid": "PRXORG482915"
    }
    ```
    """
    return await service.create_organization(request.model_dump(), current_user)


@router.get("", response_model=OrganizationListResponse, summary="List Organizations")
async def list_organizations(
    search: Optional[str] = Query(None, description="Search by organization name"),
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE or INACTIVE"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(50, ge=1, le=200, description="Pagination limit"),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** List all organizations with search, filter, and pagination.

    **Access:** Platform Admin only

    **Query Parameters:**
    - `search` — partial match on organization_name
    - `status` — ACTIVE or INACTIVE
    - `skip` / `limit` — pagination

    **Response:**
    ```json
    {
      "total": 25,
      "organizations": [
        {
          "id": "...",
          "organization_gid": "PRXORG482915",
          "organization_name": "XYZ Pharma Pvt Ltd",
          "status": "ACTIVE",
          ...
        }
      ]
    }
    ```
    """
    return await service.list_organizations(search, status, skip, limit)


@router.get("/{org_id}", response_model=OrganizationResponse, summary="Get Organization")
async def get_organization(
    org_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Get single organization details by ID.

    **Access:** Platform Admin only

    **Response:** Full organization document.
    """
    return await service.get_organization(org_id)


@router.put("/{org_id}", response_model=MessageResponse, summary="Update Organization")
async def update_organization(
    org_id: str,
    request: OrganizationUpdateRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Update organization details. Only send fields you want to change.

    **Access:** Platform Admin only

    **Request Body (partial update):**
    ```json
    {
      "organization_name": "XYZ Pharma Updated",
      "city": "Mumbai"
    }
    ```

    **Response:**
    ```json
    { "message": "Organization updated successfully" }
    ```
    """
    return await service.update_organization(org_id, request.model_dump(exclude_none=True))


@router.post("/{org_id}/activate", response_model=MessageResponse, summary="Activate Organization")
async def activate_organization(
    org_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Reactivate a previously deactivated organization.

    **Access:** Platform Admin only

    **Response:**
    ```json
    { "message": "Organization active successfully" }
    ```
    """
    return await service.toggle_status(org_id, "ACTIVE")


@router.post("/{org_id}/deactivate", response_model=MessageResponse, summary="Deactivate Organization")
async def deactivate_organization(
    org_id: str,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Deactivate an organization (soft delete — no hard delete).

    **Access:** Platform Admin only

    **Response:**
    ```json
    { "message": "Organization inactive successfully" }
    ```
    """
    return await service.toggle_status(org_id, "INACTIVE")
