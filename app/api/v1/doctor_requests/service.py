"""
Doctor Requests service — DRX Doctor Platform

Flow:
  1. MRX Admin creates request → PENDING
  2. Doctor accepts → still PENDING (waiting for admin)
  3. Doctor rejects → REJECTED (done, never reaches admin)
  4. DRX Admin approves → APPROVED (auto-link + sync to MRX)
  5. DRX Admin rejects → REJECTED (done)
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.doctor_request_model import DoctorRequestInDB, RequestStatus
from app.config import settings
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.doctor_requests.service")


async def create_request(username: str, organization_gid: str, requested_by: str) -> Dict[str, Any]:
    """MRX Admin requests a doctor to join their organization."""
    db = get_database()

    # Validate doctor exists
    doctor = await db.doctors.find_one({"username": username})
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # Validate organization exists by GID
    org = await db.organizations.find_one({"organization_gid": organization_gid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    organization_id = str(org["_id"])

    # Check if doctor is already linked to this org
    existing_link = await db.doctor_organizations.find_one({
        "doctor_id": str(doctor["_id"]),
        "organization_id": organization_id,
        "status": "ACTIVE"
    })
    if existing_link:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Doctor is already linked to this organization")

    # Check for duplicate pending request
    existing_request = await db.doctor_requests.find_one({
        "doctor_id": str(doctor["_id"]),
        "organization_id": organization_id,
        "status": RequestStatus.PENDING
    })
    if existing_request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A pending request already exists for this doctor and organization")

    # Create the request
    request_doc = DoctorRequestInDB(
        doctor_gid=doctor.get("doctor_gid", ""),
        doctor_id=str(doctor["_id"]),
        doctor_username=username,
        organization_id=organization_id,
        organization_gid=organization_gid,
        organization_name=org.get("organization_name", ""),
        requested_by=requested_by,
        status=RequestStatus.PENDING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.doctor_requests.insert_one(request_doc.model_dump())

    # Notify doctor
    try:
        from app.api.v1.notifications.service import create_notification
        await create_notification(
            user_id=str(doctor["_id"]),
            title="Organization Request",
            message=f"{org.get('organization_name', 'An organization')} wants to add you to their network.",
            notification_type="doctor_request",
            metadata={"request_id": str(result.inserted_id), "organization_id": organization_id}
        )
    except Exception as e:
        logger.warning(f"Notification failed (create_request): {e}")

    return {
        "message": "Request sent to doctor",
        "request_id": str(result.inserted_id),
        "status": RequestStatus.PENDING
    }


async def get_requests_by_org(organization_gid: str) -> Dict[str, Any]:
    """MRX Admin views all requests for their organization."""
    db = get_database()

    org = await db.organizations.find_one({"organization_gid": organization_gid})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    requests = await db.doctor_requests.find({
        "organization_id": str(org["_id"])
    }).sort("created_at", -1).to_list(length=200)

    results = []
    for req in requests:
        results.append({
            "id": str(req["_id"]),
            "doctor_gid": req["doctor_gid"],
            "doctor_username": req.get("doctor_username", ""),
            "organization_gid": req.get("organization_gid", ""),
            "organization_name": req.get("organization_name", ""),
            "requested_by": req["requested_by"],
            "status": req["status"],
            "doctor_accepted": req.get("doctor_accepted"),
            "admin_accepted": req.get("admin_accepted"),
            "rejected_by": req.get("rejected_by"),
            "created_at": req["created_at"],
            "doctor_responded_at": req.get("doctor_responded_at"),
            "admin_responded_at": req.get("admin_responded_at")
        })

    return {"total": len(results), "requests": results}


async def get_doctor_pending_requests(doctor_id: str) -> Dict[str, Any]:
    """Get pending requests for a doctor (where doctor hasn't responded yet)."""
    db = get_database()

    requests = await db.doctor_requests.find({
        "doctor_id": doctor_id,
        "status": RequestStatus.PENDING,
        "doctor_accepted": None
    }).sort("created_at", -1).to_list(length=100)

    results = []
    for req in requests:
        results.append({
            "id": str(req["_id"]),
            "doctor_gid": req["doctor_gid"],
            "organization_id": req["organization_id"],
            "organization_gid": req.get("organization_gid", ""),
            "organization_name": req.get("organization_name", ""),
            "requested_by": req["requested_by"],
            "status": req["status"],
            "created_at": req["created_at"]
        })

    return {"total": len(results), "requests": results}


async def doctor_accept(request_id: str, doctor_id: str) -> Dict[str, Any]:
    """Doctor accepts the request → still PENDING, waiting for admin."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["doctor_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This request is not for you")

    if req["status"] != RequestStatus.PENDING or req.get("doctor_accepted") is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already responded to")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "doctor_accepted": True,
            "doctor_responded_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )

    # Notify DRX admins
    try:
        from app.api.v1.notifications.service import create_notification
        admins = await db.admin_users.find({"is_active": True}, {"_id": 1}).to_list(length=50)
        for admin in admins:
            await create_notification(
                user_id=str(admin["_id"]),
                title="Doctor Request Awaiting Approval",
                message=f"Doctor {req.get('doctor_username', req['doctor_gid'])} accepted request from {req.get('organization_name', '')}. Needs your approval.",
                notification_type="doctor_request_approval",
                metadata={"request_id": request_id, "organization_id": req["organization_id"]}
            )
    except Exception as e:
        logger.warning(f"Notification failed (doctor_accept): {e}")

    return {"message": "Request accepted. Awaiting DRX admin approval.", "status": RequestStatus.PENDING}


async def doctor_reject(request_id: str, doctor_id: str) -> Dict[str, Any]:
    """Doctor rejects → REJECTED. Never reaches admin."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["doctor_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This request is not for you")

    if req["status"] != RequestStatus.PENDING or req.get("doctor_accepted") is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already responded to")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.REJECTED,
            "doctor_accepted": False,
            "rejected_by": "doctor",
            "doctor_responded_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": "Request rejected.", "status": RequestStatus.REJECTED}


async def get_admin_pending_requests() -> Dict[str, Any]:
    """Get requests where doctor accepted but admin hasn't responded yet."""
    db = get_database()

    requests = await db.doctor_requests.find({
        "status": RequestStatus.PENDING,
        "doctor_accepted": True,
        "admin_accepted": None
    }).sort("doctor_responded_at", -1).to_list(length=100)

    results = []
    for req in requests:
        results.append({
            "id": str(req["_id"]),
            "doctor_gid": req["doctor_gid"],
            "doctor_username": req.get("doctor_username", ""),
            "doctor_id": req["doctor_id"],
            "organization_id": req["organization_id"],
            "organization_gid": req.get("organization_gid", ""),
            "organization_name": req.get("organization_name", ""),
            "requested_by": req["requested_by"],
            "status": req["status"],
            "created_at": req["created_at"],
            "doctor_responded_at": req.get("doctor_responded_at")
        })

    return {"total": len(results), "requests": results}


async def admin_approve(request_id: str, admin_username: str, token: str) -> Dict[str, Any]:
    """DRX Admin approves → APPROVED, creates relationship, syncs to MRX."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["status"] != RequestStatus.PENDING or req.get("doctor_accepted") != True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not ready for admin approval")

    # Update request status
    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.APPROVED,
            "admin_accepted": True,
            "admin_responded_at": datetime.utcnow(),
            "admin_responded_by": admin_username,
            "updated_at": datetime.utcnow()
        }}
    )

    # Create ACTIVE relationship in doctor_organizations
    existing_link = await db.doctor_organizations.find_one({
        "doctor_id": req["doctor_id"],
        "organization_id": req["organization_id"]
    })

    if not existing_link:
        await db.doctor_organizations.insert_one({
            "doctor_id": req["doctor_id"],
            "organization_id": req["organization_id"],
            "status": "ACTIVE",
            "requested_by": admin_username,
            "requested_at": datetime.utcnow(),
            "joined_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
    elif existing_link.get("status") != "ACTIVE":
        await db.doctor_organizations.update_one(
            {"_id": existing_link["_id"]},
            {"$set": {"status": "ACTIVE", "joined_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )

    # Sync doctor to MRX
    try:
        from app.services.mrx_client import mrx_client
        doctor = await db.doctors.find_one({"_id": ObjectId(req["doctor_id"])})
        if doctor:
            await mrx_client.request(
                org_id=req["organization_id"],
                method="POST",
                endpoint=f"{settings.MRX_API_PREFIX}/doctors/register",
                token=token,
                body={
                    "doctor_gid": doctor.get("doctor_gid", ""),
                    "name": doctor.get("name", ""),
                    "email": doctor.get("email", ""),
                    "phone": doctor.get("phone", ""),
                    "username": doctor.get("username", ""),
                    "specialization": doctor.get("specialization"),
                    "hospital": doctor.get("hospital")
                }
            )
    except Exception as e:
        logger.warning(f"MRX sync failed (admin_approve): {e}")  # Don't fail approval if MRX sync fails

    # Notify doctor
    try:
        from app.api.v1.notifications.service import create_notification
        await create_notification(
            user_id=req["doctor_id"],
            title="Request Approved",
            message=f"You are now connected to {req.get('organization_name', '')}.",
            notification_type="doctor_request_approved",
            metadata={"organization_id": req["organization_id"]}
        )
    except Exception as e:
        logger.warning(f"Notification failed (admin_approve): {e}")

    return {"message": "Request approved. Doctor linked to organization.", "status": RequestStatus.APPROVED}


async def admin_reject(request_id: str, admin_username: str) -> Dict[str, Any]:
    """DRX Admin rejects the request → REJECTED."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["status"] != RequestStatus.PENDING or req.get("doctor_accepted") != True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is not ready for admin action")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.REJECTED,
            "admin_accepted": False,
            "rejected_by": "admin",
            "admin_responded_at": datetime.utcnow(),
            "admin_responded_by": admin_username,
            "updated_at": datetime.utcnow()
        }}
    )

    # Notify doctor
    try:
        from app.api.v1.notifications.service import create_notification
        await create_notification(
            user_id=req["doctor_id"],
            title="Request Rejected",
            message=f"Your request to join {req.get('organization_name', '')} was rejected by the platform admin.",
            notification_type="doctor_request_rejected",
            metadata={"organization_id": req["organization_id"]}
        )
    except Exception as e:
        logger.warning(f"Notification failed (admin_reject): {e}")

    return {"message": "Request rejected.", "status": RequestStatus.REJECTED}
