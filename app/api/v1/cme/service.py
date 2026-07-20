"""
CME service — DRX Doctor Platform

Ownership:
  - MRX owns: Creating CME events, event data
  - DRX owns: Doctor registrations, My CME, attendance

Flow for listing events:
  Doctor → DRX → mrx_client → MRX /integration/cme → events

Flow for registration:
  Doctor registers → stored in DRX cme_registrations collection
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.services.mrx_client import mrx_client, MRXClientError


async def _verify_doctor_org_access(doctor_id: str, org_id: str):
    """Verify doctor has ACTIVE relationship with org"""
    db = get_database()
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")
    rel = await db.doctor_organizations.find_one({
        "doctor_id": doctor_id, "organization_id": org_id, "status": "ACTIVE"
    })
    if not rel:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not connected to this organization")


async def list_org_cme_events(
    org_id: str,
    doctor_id: str,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """Fetch CME events from org's MRX backend"""
    await _verify_doctor_org_access(doctor_id, org_id)

    params = {"skip": skip, "limit": limit}
    if status_filter:
        params["status"] = status_filter

    try:
        return await mrx_client.request(org_id, "GET", "/api/v1/integration/cme", params=params)
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def register_for_event(
    org_id: str,
    event_data: Dict[str, Any],
    doctor_id: str,
    doctor_name: str
) -> Dict[str, str]:
    """
    Doctor registers for a CME event.
    Registration stored in DRX's own cme_registrations collection.
    """
    db = get_database()
    await _verify_doctor_org_access(doctor_id, org_id)

    event_title = event_data.get("event_title", "")
    event_date = event_data.get("event_date")
    event_id = event_data.get("event_id")  # Reference ID from MRX (for display)

    if not event_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="event_title is required")

    # Check duplicate registration
    existing = await db.cme_registrations.find_one({
        "doctor_id": doctor_id,
        "organization_id": org_id,
        "event_id": event_id
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already registered for this event")

    registration = {
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "organization_id": org_id,
        "event_id": event_id,
        "event_title": event_title,
        "event_date": event_date,
        "status": "REGISTERED",  # REGISTERED, ATTENDED, ABSENT, CANCELLED
        "registered_at": datetime.utcnow(),
        "attended_at": None,
        "cancelled_at": None,
        "created_at": datetime.utcnow()
    }

    await db.cme_registrations.insert_one(registration)
    return {"message": f"Successfully registered for '{event_title}'"}


async def get_my_cme(doctor_id: str, status_filter: Optional[str] = None) -> Dict[str, Any]:
    """Get doctor's CME registrations (across all organizations)"""
    db = get_database()

    query = {"doctor_id": doctor_id}
    if status_filter:
        query["status"] = status_filter

    registrations = await db.cme_registrations.find(query).sort("registered_at", -1).to_list(length=200)

    for reg in registrations:
        reg["id"] = str(reg.pop("_id"))

    return {"total": len(registrations), "registrations": registrations}


async def cancel_registration(registration_id: str, doctor_id: str) -> Dict[str, str]:
    """Doctor cancels their CME registration"""
    db = get_database()

    if not ObjectId.is_valid(registration_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid registration ID")

    reg = await db.cme_registrations.find_one({"_id": ObjectId(registration_id)})
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    if reg["doctor_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your registration")

    if reg["status"] != "REGISTERED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot cancel — status is {reg['status']}")

    await db.cme_registrations.update_one(
        {"_id": ObjectId(registration_id)},
        {"$set": {"status": "CANCELLED", "cancelled_at": datetime.utcnow()}}
    )

    return {"message": "Registration cancelled"}


async def mark_attendance(registration_id: str, attended: bool, admin_user: Dict) -> Dict[str, str]:
    """Platform admin marks attendance for a registration"""
    db = get_database()

    if not ObjectId.is_valid(registration_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid registration ID")

    reg = await db.cme_registrations.find_one({"_id": ObjectId(registration_id)})
    if not reg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration not found")

    if reg["status"] == "CANCELLED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot mark attendance for cancelled registration")

    new_status = "ATTENDED" if attended else "ABSENT"
    update = {"status": new_status}
    if attended:
        update["attended_at"] = datetime.utcnow()

    await db.cme_registrations.update_one(
        {"_id": ObjectId(registration_id)},
        {"$set": update}
    )

    return {"message": f"Attendance marked: {new_status}"}
