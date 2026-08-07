"""
Integration Services Routes — Platform Admin manages trusted backend services.
"""

from fastapi import APIRouter, Depends
from app.core.auth import require_platform_admin
from app.api.v1.integration_services import service
from app.api.v1.integration_services.schemas import (
    CreateIntegrationServiceRequest, CreateIntegrationServiceResponse,
    IntegrationServiceListResponse, RotateSecretResponse, MessageResponse
)

router = APIRouter()


@router.post("", response_model=CreateIntegrationServiceResponse, status_code=201, summary="Create Integration Service")
async def create_service_endpoint(
    request: CreateIntegrationServiceRequest,
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Register a new trusted backend service (Voice Onboarding, MRX, OCR, etc.)

    **Access:** Platform Admin only

    **Request Body:**
    ```json
    {
      "service_name": "Voice Onboarding",
      "service_code": "ONBOARDING",
      "description": "Voice onboarding backend for doctor registration"
    }
    ```

    **Response (credentials shown ONCE):**
    ```json
    {
      "message": "Integration service created successfully",
      "service_id": "...",
      "service_name": "Voice Onboarding",
      "service_code": "ONBOARDING",
      "client_id": "onboarding_a1b2c3d4",
      "client_secret": "X8kQ29Lp7mF... (48 chars)",
      "status": "ACTIVE"
    }
    ```

    **Important:** The `client_secret` is shown only once. Store it in the consuming service's .env immediately.
    """
    return await service.create_service(request.model_dump())


@router.get("", response_model=IntegrationServiceListResponse, summary="List Integration Services")
async def list_services_endpoint(current_user=Depends(require_platform_admin)):
    """
    **Purpose:** List all registered integration services.

    **Access:** Platform Admin only

    **Response:** All services with status, last_used_at, etc. No secrets shown.
    """
    return await service.get_all_services()


@router.post("/{service_id}/rotate-secret", response_model=RotateSecretResponse, summary="Rotate Service Secret")
async def rotate_secret_endpoint(service_id: str, current_user=Depends(require_platform_admin)):
    """
    **Purpose:** Generate a new secret for a service. Old secret becomes invalid immediately.

    **Access:** Platform Admin only

    **Response (new secret shown ONCE):**
    ```json
    {
      "message": "Secret rotated successfully",
      "client_id": "onboarding_a1b2c3d4",
      "client_secret": "NewSecretHere..."
    }
    ```

    **After rotation:** Update the consuming service's .env with the new secret.
    """
    return await service.rotate_secret(service_id)


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
    **Purpose:** Disable a service. Its credentials will no longer be accepted for token exchange.

    **Access:** Platform Admin only
    """
    return await service.set_status(service_id, "INACTIVE")
