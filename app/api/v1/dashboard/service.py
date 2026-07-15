"""
Doctor Dashboard service — DRX owned data only (no MRX dependency)
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

    # Bonus: locations count
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


async def get_doctor_dashboard(current_user: Dict) -> Dict[str, Any]:
    """
    Build doctor's dashboard with DRX-owned data only.
    No MRX dependency.
    """
    db = get_database()
    doctor_id = current_user["_id"]

    # Get full doctor document
    doctor = await db.doctors.find_one({"_id": ObjectId(doctor_id)})
    if not doctor:
        return {"error": "Doctor not found"}

    # 1. Basic info
    basic_info = {
        "name": doctor.get("name", ""),
        "doctor_gid": doctor.get("doctor_gid", ""),
        "email": doctor.get("email", ""),
        "avatar_url": doctor.get("avatar_url"),
        "specialization": doctor.get("specialization"),
        "hospital": doctor.get("hospital"),
    }

    # 2. Profile completion
    profile_completion = _compute_profile_completion(doctor)

    # 3. Connected organizations
    org_relationships = await db.doctor_organizations.find(
        {"doctor_id": doctor_id, "status": "ACTIVE"}
    ).to_list(length=100)

    connected_orgs = []
    for rel in org_relationships:
        org = await db.organizations.find_one(
            {"_id": ObjectId(rel["organization_id"])},
            {"organization_name": 1, "organization_gid": 1, "logo": 1, "city": 1}
        )
        if org:
            connected_orgs.append({
                "organization_id": str(org["_id"]),
                "organization_gid": org.get("organization_gid", ""),
                "organization_name": org.get("organization_name", ""),
                "logo": org.get("logo"),
                "city": org.get("city"),
                "joined_at": rel.get("joined_at")
            })

    # 4. Pending org invitations
    pending_invites = await db.doctor_organizations.count_documents(
        {"doctor_id": doctor_id, "status": "PENDING"}
    )

    # 5. Locations summary
    locations = doctor.get("locations", [])
    active_locations = [loc for loc in locations if loc.get("is_active", True)]
    primary_id = doctor.get("primary_location_id")
    primary_location = None
    for loc in locations:
        if loc.get("id") == primary_id:
            primary_location = {"name": loc["name"], "city": loc.get("city", ""), "type": loc.get("type", "")}
            break

    # 6. Account status
    account_status = {
        "is_active": doctor.get("is_active", True),
        "is_email_verified": doctor.get("is_email_verified", False),
        "is_phone_verified": doctor.get("is_phone_verified", False),
        "member_since": doctor.get("created_at"),
        "last_login": doctor.get("last_login_at"),
    }

    return {
        "doctor": basic_info,
        "profile_completion": profile_completion,
        "organizations": {
            "connected": len(connected_orgs),
            "list": connected_orgs,
            "pending_invitations": pending_invites
        },
        "locations": {
            "total": len(locations),
            "active": len(active_locations),
            "primary": primary_location
        },
        "account": account_status
    }
