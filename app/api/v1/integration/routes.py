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

    **Access:** Any service with valid credentials (MRX backend)

    **Request Body:**
    ```json
    {
      "client_id": "abc_pharma_7f2a",
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

    **Validations:**
    - Organization must exist with matching client_id
    - client_secret must match stored hash
    - Organization must be ACTIVE

    **Token lifetime:** 15 minutes
    """
    db = get_database()

    # Find org by client_id
    org = await db.organizations.find_one({"client_id": request.client_id})
    if not org:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Verify secret
    if not verify_password(request.client_secret, org["client_secret_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check active
    if org.get("status") != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization is inactive")

    # Generate service token
    token = create_service_token(
        organization_id=str(org["_id"]),
        organization_name=org["organization_name"],
        client_id=org["client_id"]
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": SERVICE_TOKEN_EXPIRE_MINUTES * 60
    }


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
    from datetime import datetime
    from app.core.security import hash_password
    from app.models.doctor_model import generate_doctor_gid
    from app.config import settings

    db = get_database()

    name = request.get("name", "").strip()
    email = request.get("email", "").strip().lower()
    phone = request.get("phone", "").strip()

    if not name or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and email are required")

    # Check if doctor already exists by email
    existing = await db.doctors.find_one({"email": email})
    if existing:
        return {
            "status": "exists",
            "doctor_gid": existing.get("doctor_gid", ""),
            "message": "Doctor already exists on DRX"
        }

    # Check phone duplicate
    if phone:
        phone_exists = await db.doctors.find_one({"phone": phone})
        if phone_exists:
            return {
                "status": "exists",
                "doctor_gid": phone_exists.get("doctor_gid", ""),
                "message": "Doctor with this phone already exists on DRX"
            }

    # Generate unique GID
    doctor_gid = generate_doctor_gid()
    while await db.doctors.find_one({"doctor_gid": doctor_gid}):
        doctor_gid = generate_doctor_gid()

    # Create doctor using Pydantic model
    from app.models.doctor_model import DoctorInDB

    doctor = DoctorInDB(
        doctor_gid=doctor_gid,
        email=email,
        phone=phone,
        password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
        name=name,
        is_active=True,
        is_email_verified=False,
        is_phone_verified=False,
        locations=[],
        registered_via=org_context.get("client_id", "unknown"),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    try:
        await db.doctors.insert_one(doctor.model_dump())
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to register doctor: {str(e)}")

    return {
        "status": "created",
        "doctor_gid": doctor_gid,
        "message": "Doctor registered on DRX"
    }
