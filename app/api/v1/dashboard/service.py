"""
Doctor Dashboard service — DRX Doctor Platform
Returns everything the frontend dashboard needs in one call.
"""

from typing import Dict, Any, List
from bson import ObjectId
from app.database import get_database


def _compute_profile_completion(doctor: Dict) -> Dict[str, Any]:
    """Calculate profile completion percentage and missing fields"""
    fields = {
        "name": doctor.get("name"),
        "phone": doctor.get("phone"),
        "email": doctor.get("email"),
        "specialization": doctor.get("specialization"),
        "hospital": doctor.get("hospital"),
        "qualification": doctor.get("qualification"),
        "experience_years": doctor.get("experience_years"),
        "license_number": doctor.get("license_number"),
        "bio": doctor.get("bio"),
        "avatar_url": doctor.get("avatar_url"),
        "city": doctor.get("city"),
        "state": doctor.get("state"),
        "country": doctor.get("country"),
    }

    total = len(fields)
    filled = sum(1 for v in fields.values() if v)
    missing = [k for k, v in fields.items() if not v]
    percentage = round((filled / total) * 100)

    locations = doctor.get("locations", [])
    has_location = len(locations) > 0
    if not has_location:
        missing.append("practice_location")
        total += 1
    else:
        total += 1
        filled += 1
        percentage = round((filled / total) * 100)

    return {
        "percentage": percentage,
        "filled": filled,
        "total": total,
        "missing_fields": missing
    }


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

    # ── 2. Profile Completion ──
    profile_completion = _compute_profile_completion(doctor)

    # ── 3. Organizations ──
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

    # ── 4. Activity Summary ──
    # CME registrations
    total_cme = await db.cme_registrations.count_documents({"doctor_id": doctor_id})
    cme_attended = await db.cme_registrations.count_documents({"doctor_id": doctor_id, "status": "ATTENDED"})
    cme_upcoming = await db.cme_registrations.count_documents({"doctor_id": doctor_id, "status": "REGISTERED"})

    # Connections
    total_connections = await db.connections.count_documents({
        "$or": [{"requester_id": doctor_id}, {"receiver_id": doctor_id}],
        "status": "accepted"
    })
    pending_requests = await db.connections.count_documents({
        "receiver_id": doctor_id, "status": "pending"
    })

    # Posts
    total_posts = await db.posts.count_documents({"author_id": doctor_id, "is_active": True})

    # Notifications unread
    unread_notifications = await db.notifications.count_documents({"user_id": doctor_id, "is_read": False})

    # ── 5. Locations ──
    locations = doctor.get("locations", [])
    active_locations = [loc for loc in locations if loc.get("is_active", True)]
    primary_id = doctor.get("primary_location_id")
    primary_location = None
    for loc in locations:
        if loc.get("id") == primary_id:
            primary_location = {"name": loc["name"], "city": loc.get("city", ""), "type": loc.get("type", "")}
            break

    # ── 6. Top Doctors (suggestions to connect) ──
    # Get doctors not already connected
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

    # ── 7. Account Status ──
    account = {
        "is_active": doctor.get("is_active", True),
        "is_email_verified": doctor.get("is_email_verified", False),
        "is_phone_verified": doctor.get("is_phone_verified", False),
        "member_since": doctor.get("created_at"),
        "last_login": doctor.get("last_login_at"),
    }

    # ── MRX Dashboard Data (if org_id provided) ──
    mrx_data = None
    if org_id:
        try:
            from app.services.mrx_client import mrx_client
            mrx_data = await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/dashboard")
        except Exception:
            mrx_data = None  # MRX unavailable — dashboard still works with DRX data

    return {
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
