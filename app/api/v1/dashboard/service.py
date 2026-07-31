"""
Doctor Dashboard service — DRX Doctor Platform
Returns everything the frontend dashboard needs in one call.
"""

from typing import Dict, Any
from bson import ObjectId
from app.database import get_database


async def get_doctor_dashboard(current_user: Dict, org_id: str = None) -> Dict[str, Any]:
    """
    Build full doctor dashboard.
    If org_id is provided, also fetches pharma data from MRX in one call.
    """
    db = get_database()
    doctor_id = current_user["_id"]

    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        return {"error": "Doctor not found"}

    # ── 1. Doctor Info ──
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

    # ── 2. Organizations ──
    org_relationships = await db.doctor_organizations.find(
        {"doctor_id": doctor_id, "status": "ACTIVE"}
    ).to_list(length=100)

    connected_orgs = []
    for rel in org_relationships:
        org = await db.organizations.find_one(
            {"_id": ObjectId(rel["organization_id"])},
            {"organization_name": 1, "organization_gid": 1, "logo": 1, "city": 1, "mrx_url": 1}
        )
        if org:
            connected_orgs.append({
                "organization_id": str(org["_id"]),
                "organization_gid": org.get("organization_gid", ""),
                "organization_name": org.get("organization_name", ""),
                "logo": org.get("logo"),
                "city": org.get("city"),
                "has_mrx": bool(org.get("mrx_url")),
                "joined_at": rel.get("joined_at")
            })

    # ── 3. Activity Summary ──
    unread_notifications = await db.notifications.count_documents({"user_id": doctor_id, "is_read": False})

    # ── 4. Suggested Doctors (not already connected) ──
    connected_ids = set()
    connections = await db.connections.find(
        {"$or": [{"requester_id": doctor_id}, {"receiver_id": doctor_id}]}
    ).to_list(length=500)
    for conn in connections:
        connected_ids.add(conn["requester_id"])
        connected_ids.add(conn["receiver_id"])
    connected_ids.add(doctor_id)

    exclude_oids = [ObjectId(uid) for uid in connected_ids if ObjectId.is_valid(uid)]
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

    # ── 5. MRX Dashboard Data (if org_id provided) ──
    mrx_data = None
    if org_id:
        try:
            from app.services.mrx_client import mrx_client
            mrx_data = await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/dashboard")
        except Exception:
            mrx_data = None  # MRX unavailable — dashboard still works with DRX data

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
