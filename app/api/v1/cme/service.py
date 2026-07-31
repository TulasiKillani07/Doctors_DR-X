"""
CME service — DRX Doctor Platform

Ownership:
  - MRX owns: CME events, registrations, attendance, capacity, analytics
  - DRX owns: nothing — just forwards to MRX

DRX is the UI layer. All CME data lives in MRX.
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
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
        return await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/cme", params=params)
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def get_cme_event_detail(
    org_id: str,
    event_id: str,
    doctor_id: str,
) -> Dict[str, Any]:
    """Fetch a single CME event detail from MRX"""
    await _verify_doctor_org_access(doctor_id, org_id)

    try:
        result = await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/cme", params={"skip": 0, "limit": 200})
        events = result.get("events", [])
        event = None
        for e in events:
            if e.get("id") == event_id:
                event = e
                break

        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CME event not found")

        return event
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def register_for_event(
    org_id: str,
    event_id: str,
    current_user: Dict
) -> Dict[str, Any]:
    """Forward registration to MRX — MRX owns the registration"""
    await _verify_doctor_org_access(current_user["_id"], org_id)

    doctor_gid = current_user.get("doctor_gid", "")
    doctor_name = current_user.get("name", "")

    try:
        result = await mrx_client.request(org_id, "POST", "/mrx/api/v1/integration/cme/register", body={
            "doctor_gid": doctor_gid,
            "doctor_name": doctor_name,
            "event_id": event_id
        })
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)

    # Log activity (fire-and-forget, never breaks the flow)
    try:
        from app.services.activity_logger import log_activity
        await log_activity(current_user["_id"], org_id, "cme_registered", {
            "event_id": event_id
        })
    except Exception:
        pass

    return result


async def get_my_cme(org_id: str, current_user: Dict) -> Dict[str, Any]:
    """Fetch doctor's CME registrations from MRX"""
    await _verify_doctor_org_access(current_user["_id"], org_id)

    doctor_gid = current_user.get("doctor_gid", "")

    try:
        return await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/cme/my-registrations", params={
            "doctor_gid": doctor_gid
        })
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
