"""
Integration Routes — DRX Doctor Platform

Authentication:
- User-driven endpoints: Proxzar JWT (forwarded by MRX)
- DOBO doctor registration: Proxzar JWT with integration permissions
- Notification push: TEMPORARILY DISABLED (pending background-auth redesign)
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.database import get_database
from app.core.auth import get_current_user
from app.core.proxzar_auth import require_proxzar_auth
from fastapi import HTTPException, status
from datetime import datetime
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.integration")

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# User-driven endpoints (Proxzar JWT — forwarded by MRX)
# ══════════════════════════════════════════════════════════════

@router.get("/doctors/search", summary="Search Doctors (Integration API)")
async def search_doctors_integration(
    q: str = "",
    current_user=Depends(get_current_user)
):
    """
    **Purpose:** Search doctors on the platform (used by MRX on behalf of a logged-in user).

    **Access:** Proxzar JWT (MRX forwards the user's token)

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

    return {"total": len(doctors), "doctors": doctors}


@router.get("/doctors/{doctor_gid}", summary="Get Doctor by GID (Integration API)")
async def get_doctor_integration(
    doctor_gid: str,
    current_user=Depends(get_current_user)
):
    """
    **Purpose:** Get doctor details by GID (used by MRX after doctor accepts org request).

    **Access:** Proxzar JWT (MRX forwards the user's token)

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


# ══════════════════════════════════════════════════════════════
# DOBO Doctor Registration (Proxzar JWT with integration permissions)
# ══════════════════════════════════════════════════════════════

@router.post("/doctors/register", summary="Register Doctor (DOBO Integration)")
async def register_doctor_integration(
    request: dict,
    proxzar_identity: dict = Depends(require_proxzar_auth)
):
    """
    **Purpose:** Register a doctor on DRX. Checks duplication by email — if exists, returns existing GID.

    **Access:** Proxzar JWT with authorized integration identity (e.g. DOBO)

    **Authentication:** Proxzar-issued JWT verified via JWKS (RS256)

    **Authorization:** Caller must be registered in integration_services with:
    - `authentication_provider` = "PROXZAR"
    - `proxzar_subject` matching JWT `sub`
    - `proxzar_platform` matching JWT `platform`
    - `status` = "ACTIVE"
    - `permissions` containing "doctor:create"

    **Request Body:**
    ```json
    {
      "name": "Dr. Arjun Mehta",
      "username": "arjun_mehta",
      "email": "arjun@hospital.com",
      "phone": "9876543210",
      "password": "Doctor@123"
    }
    ```

    **Fields:**
    - `name` — Required. Full name
    - `username` — Required. Unique username (3-30 chars, alphanumeric + underscores)
    - `email` — Required. Valid email (unique)
    - `phone` — Required. 10-digit phone number (unique)
    - `password` — Required. 8-64 chars, must include uppercase, lowercase, number, and symbol

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
    # ── Authorization: verify the Proxzar identity is allowed to create doctors ──
    db = get_database()

    caller_sub = proxzar_identity.get("sub", "")
    caller_platform = proxzar_identity.get("platform", "")

    logger.info(f"DOBO auth: sub={caller_sub}, platform={caller_platform}, full_claims={proxzar_identity}")

    # Look up the integration service record by sub (+ platform if present)
    lookup_query = {
        "authentication_provider": "PROXZAR",
        "proxzar_subject": caller_sub
    }
    if caller_platform:
        lookup_query["proxzar_platform"] = caller_platform

    service_record = await db.integration_services.find_one(lookup_query)

    if not service_record:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No authorized integration found for sub={caller_sub}, platform={caller_platform}"
        )

    if service_record.get("status") != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Integration service is inactive"
        )

    permissions = service_record.get("permissions", [])
    if "doctor:create" not in permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Integration does not have 'doctor:create' permission"
        )

    # Update last_used_at
    await db.integration_services.update_one(
        {"_id": service_record["_id"]},
        {"$set": {"last_used_at": datetime.utcnow()}}
    )

    # ── Proceed with doctor creation ──
    from app.api.v1.doctors.service import add_single_doctor

    name = request.get("name", "").strip()
    email = request.get("email", "").strip().lower()
    phone = request.get("phone", "").strip()

    if not name or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and email are required")

    password = request.get("password", "").strip()
    if not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password is required")

    return await add_single_doctor(
        data={
            "name": name,
            "email": email,
            "phone": phone,
            "password": password,
            "username": request.get("username", "").strip().lower(),
            "specialization": request.get("specialization"),
            "hospital": request.get("hospital"),
            "qualification": request.get("qualification"),
            "license_number": request.get("license_number"),
            "registered_via": f"proxzar:{caller_sub}:{caller_platform}"
        },
        return_existing=True
    )


# ══════════════════════════════════════════════════════════════
# Notification Push — TEMPORARILY DISABLED
# ══════════════════════════════════════════════════════════════

@router.post("/notifications/push", summary="Push Notifications (DISABLED)")
async def push_notifications_integration(request: dict):
    """
    **TEMPORARILY DISABLED.**

    This endpoint is a background machine-to-machine operation.
    It previously used Service JWT authentication which has been removed.
    A new Proxzar-based background authentication mechanism will be designed separately.
    """
    return JSONResponse(
        status_code=410,
        content={"detail": "Notification push integration is temporarily disabled pending the new Proxzar-based architecture."}
    )
