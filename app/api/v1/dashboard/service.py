"""
Doctor Dashboard service — DRX Doctor Platform
Returns everything the frontend dashboard needs in one call.
Uses asyncio.gather to parallelize independent DB queries.
"""

import asyncio
from typing import Dict, Any
from bson import ObjectId
from app.database import get_database
from app.services.helpers import get_doctor_orgs_batch


async def get_doctor_dashboard(current_user: Dict, token: str, org_id: str = None) -> Dict[str, Any]:
    """
    Build full doctor dashboard.
    If org_id is provided, also fetches pharma data from MRX in one call.

    Parallelizes 4 independent DB queries with asyncio.gather for ~3-4x latency reduction.
    """
    db = get_database()
    doctor_id = current_user["_id"]

    # ── Step 1: Fetch doctor profile (required before we can return anything) ──
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # ── Step 2: Fire all independent queries in parallel ──
    async def _fetch_orgs():
        return await get_doctor_orgs_batch(
            doctor_id,
            projection={"organization_name": 1, "organization_gid": 1, "logo": 1, "city": 1, "mrx_url": 1}
        )

    async def _fetch_unread_count():
        return await db.notifications.count_documents({"user_id": doctor_id, "is_read": False})

    async def _fetch_connections():
        """Use distinct to get only IDs, not full connection documents"""
        requester_ids = await db.connections.distinct("receiver_id", {"requester_id": doctor_id})
        receiver_ids = await db.connections.distinct("requester_id", {"receiver_id": doctor_id})
        return requester_ids + receiver_ids

    async def _fetch_mrx_data():
        if not org_id:
            return None
        try:
            from app.services.mrx_client import mrx_client
            return await mrx_client.request(org_id, "GET", "/mrxdb/integration/dashboard", token=token)
        except Exception:
            return None  # MRX unavailable — dashboard still works with DRX data

    # Run all 4 queries concurrently
    org_entries, unread_notifications, connection_ids, mrx_data = await asyncio.gather(
        _fetch_orgs(),
        _fetch_unread_count(),
        _fetch_connections(),
        _fetch_mrx_data(),
    )

    # ── Process results ──

    # 1. Doctor Info
    doctor_info = {
        "name": doctor.get("name", ""),
        "doctor_gid": doctor.get("doctor_gid", ""),
        "email": doctor.get("email", ""),
        "phone": doctor.get("phone", ""),
        "avatar_url": doctor.get("avatar_url"),
        "specialization": doctor.get("specialization"),
        "hospital": doctor.get("hospital"),
        "qualification": doctor.get("qualification"),
    }

    # 2. Organizations
    connected_orgs = []
    for entry in org_entries:
        org = entry["_org_doc"]
        connected_orgs.append({
            "organization_id": str(org["_id"]),
            "organization_gid": org.get("organization_gid", ""),
            "organization_name": org.get("organization_name", ""),
            "logo": org.get("logo"),
            "city": org.get("city"),
            "has_mrx": bool(org.get("mrx_url")),
            "joined_at": entry.get("joined_at")
        })

    # 3. Suggested Doctors (depends on connections result)
    excluded_ids = set(connection_ids)
    excluded_ids.add(doctor_id)

    exclude_oids = [ObjectId(uid) for uid in excluded_ids if ObjectId.is_valid(uid)]
    suggested_doctors = await db.doctors.find(
        {"_id": {"$nin": exclude_oids}, "is_active": True},
        {"name": 1, "specialization": 1, "avatar_url": 1, "doctor_gid": 1}
    ).limit(5).to_list(length=5)

    suggestions = []
    for doc in suggested_doctors:
        suggestions.append({
            "id": str(doc["_id"]),
            "name": doc.get("name", ""),
            "doctor_gid": doc.get("doctor_gid", ""),
            "specialization": doc.get("specialization"),
            "avatar_url": doc.get("avatar_url")
        })

    return {
        "doctor_info": doctor_info,
        "organizations": {
            "connected": len(connected_orgs),
            "list": connected_orgs
        },
        "activity_summary": {
            "unread_notifications": unread_notifications
        },
        "suggested_doctors": suggestions,
        "mrx_data": mrx_data
    }
