"""
My Organizations service — DRX Doctor Platform
Doctor views their connected organizations
"""

from typing import Dict, Any
from bson import ObjectId
from app.database import get_database


async def get_my_organizations(current_user: Dict) -> Dict[str, Any]:
    """Get organizations the doctor is connected to (ACTIVE relationships)"""
    db = get_database()
    doctor_id = current_user["_id"]

    # Find active relationships
    relationships = await db.doctor_organizations.find(
        {"doctor_id": doctor_id, "status": "ACTIVE"}
    ).to_list(length=100)

    organizations = []
    for rel in relationships:
        org = await db.organizations.find_one(
            {"_id": ObjectId(rel["organization_id"])},
            {
                "organization_gid": 1,
                "organization_name": 1,
                "logo": 1,
                "contact_email": 1,
                "city": 1,
                "state": 1,
                "country": 1,
                "status": 1
            }
        )
        if org:
            organizations.append({
                "organization_id": str(org["_id"]),
                "organization_gid": org.get("organization_gid", ""),
                "organization_name": org.get("organization_name", ""),
                "logo": org.get("logo"),
                "contact_email": org.get("contact_email"),
                "city": org.get("city"),
                "state": org.get("state"),
                "country": org.get("country"),
                "org_status": org.get("status"),
                "joined_at": rel.get("joined_at"),
                "relationship_status": rel.get("status")
            })

    return {"total": len(organizations), "organizations": organizations}


async def get_pending_invitations(current_user: Dict) -> Dict[str, Any]:
    """Get pending org invitations — currently no invitation system, returns empty"""
    return {"total": 0, "invitations": []}


async def respond_to_invitation(relationship_id: str, action: str, current_user: Dict) -> Dict[str, str]:
    """No invitation system — relationships are immediately ACTIVE"""
    from fastapi import HTTPException, status
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No invitation system. Doctor-organization relationships are created directly by Platform Admin as ACTIVE."
    )
