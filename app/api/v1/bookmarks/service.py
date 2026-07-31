"""
Drug Bookmarks service — DRX Doctor Platform
Per-organization drug bookmarks. Stored only in DRX.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


class DrugBookmarkInDB(BaseModel):
    """Write model for drug_bookmarks collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_id: str
    organization_id: str
    drug_id: str
    drug_name: str
    bookmarked_at: datetime = Field(default_factory=datetime.utcnow)


async def add_bookmark(doctor_id: str, org_id: str, drug_id: str, drug_name: str) -> Dict[str, Any]:
    """Bookmark a drug (per org)"""
    db = get_database()

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    # Check duplicate
    existing = await db.drug_bookmarks.find_one({
        "doctor_id": doctor_id,
        "organization_id": org_id,
        "drug_id": drug_id
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drug already bookmarked")

    bookmark = DrugBookmarkInDB(
        doctor_id=doctor_id,
        organization_id=org_id,
        drug_id=drug_id,
        drug_name=drug_name,
        bookmarked_at=datetime.utcnow()
    )

    result = await db.drug_bookmarks.insert_one(bookmark.model_dump())

    # Log activity
    from app.services.activity_logger import log_activity
    await log_activity(doctor_id, org_id, "drug_bookmarked", {
        "drug_id": drug_id,
        "drug_name": drug_name
    })

    return {"message": "Drug bookmarked", "bookmark_id": str(result.inserted_id)}


async def remove_bookmark(bookmark_id: str, doctor_id: str) -> Dict[str, str]:
    """Remove a bookmark"""
    db = get_database()

    if not ObjectId.is_valid(bookmark_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bookmark ID")

    result = await db.drug_bookmarks.delete_one({
        "_id": ObjectId(bookmark_id),
        "doctor_id": doctor_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

    return {"message": "Bookmark removed"}


async def get_bookmarks(doctor_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
    """Get doctor's bookmarked drugs, optionally filtered by org"""
    db = get_database()

    query = {"doctor_id": doctor_id}
    if org_id:
        query["organization_id"] = org_id

    bookmarks = await db.drug_bookmarks.find(query).sort("bookmarked_at", -1).to_list(length=200)

    for b in bookmarks:
        b["id"] = str(b.pop("_id"))

    return {"total": len(bookmarks), "bookmarks": bookmarks}


# ══════════════════════════════════════════════════════════════
# CME Event Bookmarks
# ══════════════════════════════════════════════════════════════


class CMEBookmarkInDB(BaseModel):
    """Write model for cme_bookmarks collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_id: str
    organization_id: str
    event_id: str
    event_title: str
    bookmarked_at: datetime = Field(default_factory=datetime.utcnow)


async def add_cme_bookmark(doctor_id: str, org_id: str, event_id: str, event_title: str) -> Dict[str, Any]:
    """Bookmark a CME event (per org)"""
    db = get_database()

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    existing = await db.cme_bookmarks.find_one({
        "doctor_id": doctor_id,
        "organization_id": org_id,
        "event_id": event_id
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CME event already bookmarked")

    bookmark = CMEBookmarkInDB(
        doctor_id=doctor_id,
        organization_id=org_id,
        event_id=event_id,
        event_title=event_title,
        bookmarked_at=datetime.utcnow()
    )

    result = await db.cme_bookmarks.insert_one(bookmark.model_dump())
    return {"message": "CME event bookmarked", "bookmark_id": str(result.inserted_id)}


async def remove_cme_bookmark(bookmark_id: str, doctor_id: str) -> Dict[str, str]:
    """Remove a CME bookmark"""
    db = get_database()

    if not ObjectId.is_valid(bookmark_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bookmark ID")

    result = await db.cme_bookmarks.delete_one({
        "_id": ObjectId(bookmark_id),
        "doctor_id": doctor_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

    return {"message": "CME bookmark removed"}


async def get_cme_bookmarks(doctor_id: str, org_id: Optional[str] = None) -> Dict[str, Any]:
    """Get doctor's bookmarked CME events"""
    db = get_database()

    query = {"doctor_id": doctor_id}
    if org_id:
        query["organization_id"] = org_id

    bookmarks = await db.cme_bookmarks.find(query).sort("bookmarked_at", -1).to_list(length=200)

    for b in bookmarks:
        b["id"] = str(b.pop("_id"))

    return {"total": len(bookmarks), "bookmarks": bookmarks}


# ══════════════════════════════════════════════════════════════
# Post Bookmarks (DRX Feed Posts)
# ══════════════════════════════════════════════════════════════


class PostBookmarkInDB(BaseModel):
    """Write model for post_bookmarks collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_id: str
    post_id: str
    post_author_name: str
    post_content_preview: str = Field(default="", max_length=200)
    bookmarked_at: datetime = Field(default_factory=datetime.utcnow)


async def add_post_bookmark(doctor_id: str, post_id: str, post_author_name: str, post_content_preview: str) -> Dict[str, Any]:
    """Bookmark a feed post"""
    db = get_database()

    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    # Verify post exists
    post = await db.posts.find_one({"_id": ObjectId(post_id), "is_active": True})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Check duplicate
    existing = await db.post_bookmarks.find_one({
        "doctor_id": doctor_id,
        "post_id": post_id
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post already bookmarked")

    bookmark = PostBookmarkInDB(
        doctor_id=doctor_id,
        post_id=post_id,
        post_author_name=post_author_name,
        post_content_preview=post_content_preview[:200],
        bookmarked_at=datetime.utcnow()
    )

    result = await db.post_bookmarks.insert_one(bookmark.model_dump())

    from app.services.activity_logger import log_activity
    await log_activity(doctor_id, "drx_platform", "post_bookmarked", {"post_id": post_id})

    return {"message": "Post bookmarked", "bookmark_id": str(result.inserted_id)}


async def remove_post_bookmark(bookmark_id: str, doctor_id: str) -> Dict[str, str]:
    """Remove a post bookmark"""
    db = get_database()

    if not ObjectId.is_valid(bookmark_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bookmark ID")

    result = await db.post_bookmarks.delete_one({
        "_id": ObjectId(bookmark_id),
        "doctor_id": doctor_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")

    return {"message": "Post bookmark removed"}


async def get_post_bookmarks(doctor_id: str) -> Dict[str, Any]:
    """Get doctor's bookmarked posts"""
    db = get_database()

    bookmarks = await db.post_bookmarks.find(
        {"doctor_id": doctor_id}
    ).sort("bookmarked_at", -1).to_list(length=200)

    for b in bookmarks:
        b["id"] = str(b.pop("_id"))

    return {"total": len(bookmarks), "bookmarks": bookmarks}
