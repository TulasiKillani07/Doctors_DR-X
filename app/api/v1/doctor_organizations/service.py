"""
Doctor-Organization relationship service
"""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.models.doctor_organization_model import DoctorOrganizationInDB, RelationshipStatus
from app.services.helpers import get_or_404


async def create_relationship(doctor_id: str, organization_id: str, admin_user: Dict) -> Dict[str, Any]:
    """Create a new doctor-organization relationship (starts as PENDING)"""
    db = get_database()

    # Validate doctor and org exist (raises 400/404 automatically)
    await get_or_404("doctors", doctor_id, {"_id": 1}, detail="Doctor not found")
    await get_or_404("organizations", organization_id, {"_id": 1}, detail="Organization not found")

    # Check duplicate
    existing = await db.doctor_organizations.find_one({
        "doctor_id": doctor_id,
        "organization_id": organization_id
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Relationship already exists (status: {existing['status']})"
        )

    relationship = DoctorOrganizationInDB(
        doctor_id=doctor_id,
        organization_id=organization_id,
        status=RelationshipStatus.ACTIVE,
        requested_by=admin_user["_id"],
        requested_at=datetime.utcnow(),
        joined_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.doctor_organizations.insert_one(relationship.model_dump())

    return {
        "message": "Doctor linked to organization (ACTIVE)",
        "relationship_id": str(result.inserted_id)
    }


async def get_relationship(rel_id: str) -> Dict[str, Any]:
    """Get a single relationship by ID"""
    rel = await get_or_404("doctor_organizations", rel_id, detail="Relationship not found")
    rel["id"] = str(rel.pop("_id"))
    return rel


async def list_relationships(
    doctor_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """List relationships with filters"""
    db = get_database()

    query = {}
    if doctor_id:
        query["doctor_id"] = doctor_id
    if organization_id:
        query["organization_id"] = organization_id
    if status_filter:
        query["status"] = status_filter

    total = await db.doctor_organizations.count_documents(query)
    rels = await db.doctor_organizations.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for rel in rels:
        rel["id"] = str(rel.pop("_id"))

    return {"total": total, "relationships": rels}


async def update_status(rel_id: str, new_status: str) -> Dict[str, Any]:
    """Update relationship status"""
    db = get_database()

    valid_statuses = {"ACTIVE", "REJECTED", "REMOVED"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Status must be one of: {', '.join(valid_statuses)}"
        )

    # Validates ObjectId format and existence in one call
    await get_or_404("doctor_organizations", rel_id, {"_id": 1}, detail="Relationship not found")

    now = datetime.utcnow()
    update_fields = {"status": new_status, "updated_at": now}

    if new_status == "ACTIVE":
        update_fields["responded_at"] = now
        update_fields["joined_at"] = now
    elif new_status == "REJECTED":
        update_fields["responded_at"] = now
    elif new_status == "REMOVED":
        update_fields["removed_at"] = now

    await db.doctor_organizations.update_one(
        {"_id": ObjectId(rel_id)},
        {"$set": update_fields}
    )

    return {"message": f"Relationship status updated to {new_status}"}
