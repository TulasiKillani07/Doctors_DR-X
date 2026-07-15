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
    """Get pending org invitations for the doctor"""
    db = get_database()
    doctor_id = current_user["_id"]

    relationships = await db.doctor_organizations.find(
        {"doctor_id": doctor_id, "status": "PENDING"}
    ).to_list(length=100)

    invitations = []
    for rel in relationships:
        org = await db.organizations.find_one(
            {"_id": ObjectId(rel["organization_id"])},
            {"organization_gid": 1, "organization_name": 1, "logo": 1, "city": 1}
        )
        if org:
            invitations.append({
                "relationship_id": str(rel["_id"]),
                "organization_id": str(org["_id"]),
                "organization_gid": org.get("organization_gid", ""),
                "organization_name": org.get("organization_name", ""),
                "logo": org.get("logo"),
                "city": org.get("city"),
                "requested_at": rel.get("requested_at")
            })

    return {"total": len(invitations), "invitations": invitations}


async def respond_to_invitation(relationship_id: str, action: str, current_user: Dict) -> Dict[str, str]:
    """Doctor accepts or rejects an organization invitation"""
    from datetime import datetime
    from fastapi import HTTPException, status
    db = get_database()

    if not ObjectId.is_valid(relationship_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid relationship ID")

    rel = await db.doctor_organizations.find_one({"_id": ObjectId(relationship_id)})
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    if rel["doctor_id"] != current_user["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invitation")

    if rel["status"] != "PENDING":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invitation already {rel['status']}")

    if action == "accept":
        await db.doctor_organizations.update_one(
            {"_id": ObjectId(relationship_id)},
            {"$set": {"status": "ACTIVE", "responded_at": datetime.utcnow(), "joined_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        return {"message": "Invitation accepted. You are now connected to this organization."}

    elif action == "reject":
        await db.doctor_organizations.update_one(
            {"_id": ObjectId(relationship_id)},
            {"$set": {"status": "REJECTED", "responded_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        return {"message": "Invitation rejected."}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Action must be 'accept' or 'reject'")
