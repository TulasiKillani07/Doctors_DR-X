"""
Integration Routes — Service-to-Service APIs
Protected by Service JWT (not Doctor/Admin JWT)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.database import get_database
from app.core.security import verify_password
from app.core.service_auth import create_service_token, require_service_auth, SERVICE_TOKEN_EXPIRE_MINUTES
from fastapi import HTTPException, status

router = APIRouter()


# ── Schemas ──

class ServiceTokenRequest(BaseModel):
    client_id: str = Field(..., description="Organization client_id")
    client_secret: str = Field(..., description="Organization client_secret")


class ServiceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = Field(description="Token lifetime in seconds")


# ── Auth Endpoint ──

@router.post("/auth/service-token", response_model=ServiceTokenResponse, summary="Get Service Token")
async def get_service_token(request: ServiceTokenRequest):
    """
    **Purpose:** Exchange client_id + client_secret for a short-lived Service JWT.

    **Access:** Any registered integration service or organization with valid credentials.

    **Request Body:**
    ```json
    {
      "client_id": "onboarding_a1b2c3d4",
      "client_secret": "X8kQ29Lp7mF..."
    }
    ```

    **Response:**
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIs...",
      "token_type": "Bearer",
      "expires_in": 900
    }
    ```

    **Credential sources (checked in order):**
    1. `integration_services` collection (Voice Onboarding, OCR, etc.)
    2. `organizations` collection (MRX backends — backward compatible)

    **Token lifetime:** 15 minutes
    """
    db = get_database()

    # 1. Check integration_services first (new way)
    svc = await db.integration_services.find_one({"client_id": request.client_id})
    if svc:
        if svc.get("status") != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service is inactive")
        if not verify_password(request.client_secret, svc["client_secret_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        # Update last_used_at
        from app.api.v1.integration_services.service import update_last_used
        await update_last_used(request.client_id)

        token = create_service_token(
            organization_id=svc.get("service_code", ""),
            organization_name=svc["service_name"],
            client_id=svc["client_id"]
        )
        return {"access_token": token, "token_type": "Bearer", "expires_in": SERVICE_TOKEN_EXPIRE_MINUTES * 60}

    # 2. Fall back to organizations (backward compatible with MRX)
    org = await db.organizations.find_one({"client_id": request.client_id})
    if not org:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(request.client_secret, org["client_secret_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if org.get("status") != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive")

    token = create_service_token(
        organization_id=str(org["_id"]),
        organization_name=org["organization_name"],
        client_id=org["client_id"]
    )

    return {"access_token": token, "token_type": "Bearer", "expires_in": SERVICE_TOKEN_EXPIRE_MINUTES * 60}


# ── Protected Integration Endpoints (require Service JWT) ──

@router.get("/doctors/search", summary="Search Doctors (Service API)")
async def search_doctors_integration(
    q: str = "",
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** Search doctors on the platform (used by MRX to find doctors).

    **Access:** Service JWT only (backend-to-backend)

    **Query:** `q` — search by name or doctor_gid

    **Response:** List of matching doctors (basic info only — no sensitive data)
    """
    db = get_database()

    query = {"is_active": True}
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"doctor_gid": {"$regex": q, "$options": "i"}}
        ]

    doctors = await db.doctors.find(query, {
        "_id": 0,
        "doctor_gid": 1,
        "name": 1,
        "email": 1,
        "phone": 1
    }).limit(50).to_list(length=50)

    return {"total": len(doctors), "doctors": doctors, "caller": org_context["client_id"]}


@router.get("/doctors/{doctor_gid}", summary="Get Doctor by GID (Service API)")
async def get_doctor_integration(
    doctor_gid: str,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** Get doctor details by GID (used by MRX after doctor accepts org request).

    **Access:** Service JWT only (backend-to-backend)

    **Response:** Doctor basic profile (no password hash, no internal IDs)
    """
    db = get_database()

    doctor = await db.doctors.find_one({"doctor_gid": doctor_gid}, {
        "_id": 0,
        "password_hash": 0
    })

    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    return doctor


@router.post("/doctors/register", summary="Register Doctor (Service API)")
async def register_doctor_integration(
    request: dict,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** MRX registers a doctor on DRX. Checks duplication by email — if exists, returns existing GID.

    **Access:** Service JWT only (backend-to-backend)

    **Request Body:**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "email": "arjun@hospital.com",
      "phone": "9876543210"
    }
    ```

    **Response (new doctor):**
    ```json
    {
      "status": "created",
      "doctor_gid": "PRXDOC482915",
      "message": "Doctor registered on DRX"
    }
    ```

    **Response (already exists):**
    ```json
    {
      "status": "exists",
      "doctor_gid": "PRXDOC482915",
      "message": "Doctor already exists on DRX"
    }
    ```
    """
    from app.api.v1.doctors.service import add_single_doctor

    name = request.get("name", "").strip()
    email = request.get("email", "").strip().lower()
    phone = request.get("phone", "").strip()

    if not name or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and email are required")

    # Pass all fields through — add_single_doctor stores whatever is provided
    return await add_single_doctor(
        data={
            "name": name,
            "email": email,
            "phone": phone,
            "specialization": request.get("specialization"),
            "hospital": request.get("hospital"),
            "qualification": request.get("qualification"),
            "license_number": request.get("license_number"),
            "registered_via": org_context.get("client_id", "unknown")
        },
        return_existing=True
    )


# ══════════════════════════════════════════════════════════════
# Notification Push (MRX → DRX: new drug, new CME event)
# ══════════════════════════════════════════════════════════════

@router.post("/notifications/push", summary="Push Notifications to Doctors (Service API)")
async def push_notifications_integration(
    request: dict,
    org_context=Depends(require_service_auth)
):
    """
    **Purpose:** MRX pushes notifications to all doctors connected to this organization.
    Used when a new drug is launched or new CME event is created.

    **Access:** Service JWT only (backend-to-backend)

    **Request Body:**
    ```json
    {
      "title": "New Drug Launched",
      "message": "Paracetamol 500mg is now available",
      "type": "new_drug",
      "metadata": { "drug_id": "6a69e619...", "drug_name": "Paracetamol 500mg" }
    }
    ```

    **Types:** `new_drug`, `new_cme_event`

    **Response:**
    ```json
    { "status": "ok", "notified_count": 15 }
    ```
    """
    from app.api.v1.notifications.service import create_notification
    from bson import ObjectId

    db = get_database()

    title = request.get("title", "")
    message = request.get("message", "")
    notification_type = request.get("type", "general")
    metadata = request.get("metadata", {})
    org_id = org_context.get("organization_id", "")

    if not title or not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title and message are required")

    # Find all doctors connected to this organization
    relationships = await db.doctor_organizations.find(
        {"organization_id": org_id, "status": "ACTIVE"}
    ).to_list(length=5000)

    doctor_ids = [rel["doctor_id"] for rel in relationships]

    # Create notification for each connected doctor
    notified = 0
    for doctor_id in doctor_ids:
        try:
            await create_notification(
                user_id=doctor_id,
                title=title,
                message=message,
                notification_type=notification_type,
                metadata={**metadata, "organization_id": org_id}
            )
            notified += 1
        except Exception:
            pass  # Don't fail entire batch if one notification fails

    return {"status": "ok", "notified_count": notified}
