"""
Doctor Requests service — DRX Doctor Platform

Flow:
  1. MRX Admin creates request → PENDING_DOCTOR
  2. Doctor accepts → PENDING_ADMIN (or rejects → REJECTED_BY_DOCTOR)
  3. DRX Admin approves → APPROVED + auto-link + sync to MRX (or rejects → REJECTED_BY_ADMIN)
"""

from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.doctor_request_model import DoctorRequestInDB, RequestStatus
from app.config import settings


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
        "status": {"$in": [RequestStatus.PENDING_DOCTOR, RequestStatus.PENDING_ADMIN]}
    })
    if existing_request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A pending request already exists for this doctor and organization")

    # Create the request
    request_doc = DoctorRequestInDB(
        doctor_gid=doctor.get("doctor_gid", ""),
        doctor_id=str(doctor["_id"]),
        organization_id=organization_id,
        organization_name=org.get("organization_name", ""),
        requested_by=requested_by,
        status=RequestStatus.PENDING_DOCTOR,
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
    except Exception:
        pass  # Don't fail request creation if notification fails

    return {
        "message": "Request sent to doctor",
        "request_id": str(result.inserted_id),
        "status": RequestStatus.PENDING_DOCTOR
    }


async def get_doctor_pending_requests(doctor_id: str) -> Dict[str, Any]:
    """Get all pending requests for a doctor."""
    db = get_database()

    requests = await db.doctor_requests.find({
        "doctor_id": doctor_id,
        "status": RequestStatus.PENDING_DOCTOR
    }).sort("created_at", -1).to_list(length=100)

    results = []
    for req in requests:
        results.append({
            "id": str(req["_id"]),
            "doctor_gid": req["doctor_gid"],
            "organization_id": req["organization_id"],
            "organization_name": req.get("organization_name", ""),
            "requested_by": req["requested_by"],
            "status": req["status"],
            "created_at": req["created_at"]
        })

    return {"total": len(results), "requests": results}


async def doctor_accept(request_id: str, doctor_id: str) -> Dict[str, Any]:
    """Doctor accepts the request → moves to PENDING_ADMIN."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["doctor_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This request is not for you")

    if req["status"] != RequestStatus.PENDING_DOCTOR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is not pending doctor action (current: {req['status']})")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.PENDING_ADMIN,
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
                message=f"Doctor {req['doctor_gid']} accepted request from {req.get('organization_name', '')}. Needs your approval.",
                notification_type="doctor_request_approval",
                metadata={"request_id": request_id, "organization_id": req["organization_id"]}
            )
    except Exception:
        pass

    return {"message": "Request accepted. Awaiting DRX admin approval.", "status": RequestStatus.PENDING_ADMIN}


async def doctor_reject(request_id: str, doctor_id: str) -> Dict[str, Any]:
    """Doctor rejects the request."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["doctor_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This request is not for you")

    if req["status"] != RequestStatus.PENDING_DOCTOR:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is not pending doctor action (current: {req['status']})")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.REJECTED_BY_DOCTOR,
            "doctor_responded_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )

    return {"message": "Request rejected.", "status": RequestStatus.REJECTED_BY_DOCTOR}


async def get_admin_pending_requests() -> Dict[str, Any]:
    """Get all requests awaiting DRX admin approval."""
    db = get_database()

    requests = await db.doctor_requests.find({
        "status": RequestStatus.PENDING_ADMIN
    }).sort("doctor_responded_at", -1).to_list(length=100)

    results = []
    for req in requests:
        results.append({
            "id": str(req["_id"]),
            "doctor_gid": req["doctor_gid"],
            "doctor_id": req["doctor_id"],
            "organization_id": req["organization_id"],
            "organization_name": req.get("organization_name", ""),
            "requested_by": req["requested_by"],
            "status": req["status"],
            "created_at": req["created_at"],
            "doctor_responded_at": req.get("doctor_responded_at")
        })

    return {"total": len(results), "requests": results}


async def admin_approve(request_id: str, admin_username: str, token: str) -> Dict[str, Any]:
    """DRX Admin approves → creates relationship + syncs doctor to MRX."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["status"] != RequestStatus.PENDING_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is not pending admin action (current: {req['status']})")

    # Update request status
    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.APPROVED,
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
    except Exception:
        pass  # Don't fail approval if MRX sync fails — can retry later

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
    except Exception:
        pass

    return {"message": "Request approved. Doctor linked to organization.", "status": RequestStatus.APPROVED}


async def admin_reject(request_id: str, admin_username: str) -> Dict[str, Any]:
    """DRX Admin rejects the request."""
    db = get_database()

    if not ObjectId.is_valid(request_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request ID")

    req = await db.doctor_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req["status"] != RequestStatus.PENDING_ADMIN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Request is not pending admin action (current: {req['status']})")

    await db.doctor_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {
            "status": RequestStatus.REJECTED_BY_ADMIN,
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
    except Exception:
        pass

    return {"message": "Request rejected.", "status": RequestStatus.REJECTED_BY_ADMIN}
