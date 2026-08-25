"""
Integration Services Routes — Platform Admin manages trusted integration services.
Authentication for these services is via Proxzar JWT.
"""

from fastapi import APIRouter, Depends
from app.core.auth import require_platform_admin
from app.api.v1.integration_services import service
from app.api.v1.integration_services.schemas import (
    CreateIntegrationServiceRequest, CreateIntegrationServiceResponse,
    IntegrationServiceListResponse, MessageResponse
)

router = APIRouter()


@router.post("", response_model=CreateIntegrationServiceResponse, status_code=201, summary="Create Integration Service")
async def create_service_endpoint(
    request: CreateIntegrationServiceRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Register a new trusted integration service (DOBO, OCR, etc.)

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "service_name": "Voice Onboarding (DOBO)",
      "service_code": "DOBO",
      "description": "Voice onboarding backend for doctor registration",
      "proxzar_subject": "rx_integration",
      "proxzar_platform": "dobo",
      "permissions": ["doctor:create"]
    }
    ```

    **Response:**
    ```json
    {
      "message": "Integration service created successfully",
      "service_id": "...",
      "service_name": "Voice Onboarding (DOBO)",
      "service_code": "DOBO",
      "status": "ACTIVE"
    }
    ```

    **How it works:** The service authenticates via Proxzar JWT. DRX matches the
    JWT's `sub` and `platform` claims against the registered `proxzar_subject` and
    `proxzar_platform` to authorize operations.
    """
    return await service.create_service(request.model_dump())


@router.get("", response_model=IntegrationServiceListResponse, summary="List Integration Services")
async def list_services_endpoint(current_user=Depends(require_platform_admin)):
    """
    **Purpose:** List all registered integration services.

    **Access:** Platform Admin only

    **Response:** All services with status, permissions, and Proxzar identity mapping.
    """
    return await service.get_all_services()


@router.patch("/{service_id}/activate", response_model=MessageResponse, summary="Activate Service")
async def activate_service_endpoint(service_id: str, current_user=Depends(require_platform_admin)):
    """
    **Purpose:** Re-enable a previously deactivated service.

    **Access:** Platform Admin only
    """
    return await service.set_status(service_id, "ACTIVE")


@router.patch("/{service_id}/deactivate", response_model=MessageResponse, summary="Deactivate Service")
async def deactivate_service_endpoint(service_id: str, current_user=Depends(require_platform_admin)):
    """
    **Purpose:** Disable a service. Its Proxzar identity will no longer be authorized.

    **Access:** Platform Admin only
    """
    return await service.set_status(service_id, "INACTIVE")
