"""
Shared service helpers — DRX Doctor Platform

Eliminates duplicate patterns across service modules:
- get_or_404: ObjectId validation + find_one + HTTPException(404)
- verify_doctor_org_access: Check doctor has ACTIVE org relationship
- get_doctor_orgs_batch: Batch fetch orgs for a doctor's relationships
- enrich_posts_with_likes: Batch like-check for a list of posts
"""

from typing import Dict, Any, List, Optional, Set
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


# ══════════════════════════════════════════════════════════════
# get_or_404 — Universal document fetch with validation
# ══════════════════════════════════════════════════════════════

async def get_or_404(
    collection_name: str,
    doc_id: str,
    projection: Optional[Dict] = None,
    detail: str = "Not found"
) -> Dict[str, Any]:
    """
    Validate ObjectId, fetch document, raise 404 if missing.

    Args:
        collection_name: MongoDB collection name (e.g. "doctors", "organizations")
        doc_id: The string _id to look up
        projection: Optional field projection dict
        detail: Custom 404 error message

    Returns:
        The document dict (with _id as ObjectId)

    Raises:
        HTTPException 400 if doc_id is not a valid ObjectId
        HTTPException 404 if document not found
    """
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ID format: {doc_id}"
        )

    db = get_database()
    collection = db[collection_name]

    doc = await collection.find_one({"_id": ObjectId(doc_id)}, projection)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return doc


# ══════════════════════════════════════════════════════════════
# verify_doctor_org_access — Shared org access check
# ══════════════════════════════════════════════════════════════

async def verify_doctor_org_access(doctor_id: str, org_id: str) -> None:
    """
    Verify the doctor has an ACTIVE relationship with the given organization.

    Raises:
        HTTPException 400 if org_id is invalid
        HTTPException 403 if no active relationship exists
    """
    if not ObjectId.is_valid(org_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization ID"
        )

    db = get_database()
    relationship = await db.doctor_organizations.find_one({
        "doctor_id": doctor_id,
        "organization_id": org_id,
        "status": "ACTIVE"
    })

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not connected to this organization"
        )


# ══════════════════════════════════════════════════════════════
# get_doctor_orgs_batch — Batch fetch connected orgs
# ══════════════════════════════════════════════════════════════

async def get_doctor_orgs_batch(
    doctor_id: str,
    projection: Optional[Dict] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all ACTIVE organizations for a doctor in two queries (relationships + orgs batch).

    Args:
        doctor_id: Doctor's string _id
        projection: Optional projection for org fields. Defaults to common fields.

    Returns:
        List of dicts with org info + joined_at from the relationship
    """
    db = get_database()

    # Default projection covers common dashboard/listing needs
    if projection is None:
        projection = {
            "organization_gid": 1,
            "organization_name": 1,
            "logo": 1,
            "city": 1,
            "state": 1,
            "country": 1,
            "status": 1,
            "mrx_url": 1,
            "contact_email": 1,
        }

    relationships = await db.doctor_organizations.find(
        {"doctor_id": doctor_id, "status": "ACTIVE"}
    ).to_list(length=100)

    if not relationships:
        return []

    org_ids = [
        ObjectId(rel["organization_id"])
        for rel in relationships
        if ObjectId.is_valid(rel["organization_id"])
    ]

    orgs_list = await db.organizations.find(
        {"_id": {"$in": org_ids}},
        projection
    ).to_list(length=len(org_ids))

    org_map = {str(org["_id"]): org for org in orgs_list}

    results = []
    for rel in relationships:
        org = org_map.get(rel["organization_id"])
        if org:
            entry = {"_org_doc": org, "joined_at": rel.get("joined_at"), "relationship_status": rel.get("status")}
            results.append(entry)

    return results


# ══════════════════════════════════════════════════════════════
# enrich_posts_with_likes — Batch like-check
# ══════════════════════════════════════════════════════════════

async def enrich_posts_with_likes(posts: List[Dict], doctor_id: str) -> List[Dict]:
    """
    For a list of post documents (with _id already converted to "id" string),
    batch-check which ones the doctor has liked and add `is_liked` field.

    Args:
        posts: List of post dicts where each has an "id" key (string post ID)
        doctor_id: The current doctor's string _id

    Returns:
        The same list with "is_liked" added to each post (mutates in place)
    """
    if not posts:
        return posts

    db = get_database()

    post_ids = [p["id"] for p in posts]
    liked_docs = await db.post_likes.find(
        {"post_id": {"$in": post_ids}, "user_id": doctor_id},
        {"post_id": 1}
    ).to_list(length=len(post_ids))

    liked_set: Set[str] = {doc["post_id"] for doc in liked_docs}

    for post in posts:
        post["is_liked"] = post["id"] in liked_set

    return posts
