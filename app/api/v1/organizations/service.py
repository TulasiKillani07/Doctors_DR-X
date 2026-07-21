"""
Organization service — CRUD for organizations collection
"""

import secrets
import re
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.core.security import hash_password
from app.models.organization_model import OrganizationInDB, generate_org_gid


def _generate_client_id(org_name: str) -> str:
    """Generate client_id from org name: lowercase, underscores, + 4 random chars"""
    slug = re.sub(r'[^a-z0-9]', '_', org_name.lower().strip())
    slug = re.sub(r'_+', '_', slug).strip('_')[:30]
    return f"{slug}_{secrets.token_hex(2)}"


def _generate_client_secret() -> str:
    """Generate a long random client_secret (64 chars)"""
    return secrets.token_urlsafe(48)


async def create_organization(data: Dict[str, Any], admin_user: Dict) -> Dict[str, Any]:
    """Create a new organization with auto-generated credentials"""
    db = get_database()

    # Generate unique GID
    org_gid = generate_org_gid()
    while await db.organizations.find_one({"organization_gid": org_gid}):
        org_gid = generate_org_gid()

    # Generate service auth credentials
    client_id = _generate_client_id(data["organization_name"])
    while await db.organizations.find_one({"client_id": client_id}):
        client_id = _generate_client_id(data["organization_name"])

    client_secret = _generate_client_secret()
    client_secret_hash = hash_password(client_secret)

    org = OrganizationInDB(
        organization_gid=org_gid,
        organization_name=data["organization_name"],
        logo=data.get("logo"),
        contact_email=data.get("contact_email"),
        contact_phone=data.get("contact_phone"),
        org_admin=data.get("org_admin"),
        admin_email=data.get("admin_email"),
        admin_phone=data.get("admin_phone"),
        address=data.get("address"),
        city=data.get("city"),
        state=data.get("state"),
        country=data.get("country"),
        pincode=data.get("pincode"),
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        mrx_url=data.get("mrx_url"),
        status="ACTIVE",
        created_by=admin_user["_id"],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    result = await db.organizations.insert_one(org.model_dump())

    # Return client_secret ONLY on creation (never again)
    return {
        "message": "Organization created successfully",
        "organization_id": str(result.inserted_id),
        "organization_gid": org_gid,
        "client_id": client_id,
        "client_secret": client_secret  # Only returned once!
    }


async def get_organization(org_id: str) -> Dict[str, Any]:
    """Get a single organization by ID"""
    db = get_database()

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    org["id"] = str(org.pop("_id"))
    return org


async def list_organizations(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """List organizations with search, filter, pagination"""
    db = get_database()

    query = {}

    if search:
        query["organization_name"] = {"$regex": search, "$options": "i"}

    if status_filter:
        query["status"] = status_filter

    total = await db.organizations.count_documents(query)
    orgs = await db.organizations.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for org in orgs:
        org["id"] = str(org.pop("_id"))

    return {"total": total, "organizations": orgs}


async def update_organization(org_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update organization fields"""
    db = get_database()

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    # Build update — only non-None fields
    update_fields = {k: v for k, v in data.items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    update_fields["updated_at"] = datetime.utcnow()

    await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": update_fields}
    )

    return {"message": "Organization updated successfully"}


async def toggle_status(org_id: str, new_status: str) -> Dict[str, Any]:
    """Activate or deactivate an organization"""
    db = get_database()

    if new_status not in ("ACTIVE", "INACTIVE"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status must be ACTIVE or INACTIVE")

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    result = await db.organizations.update_one(
        {"_id": ObjectId(org_id)},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    return {"message": f"Organization {new_status.lower()} successfully"}
