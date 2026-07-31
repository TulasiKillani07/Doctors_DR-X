"""
Drug Bookmarks Routes — DRX Doctor Platform
Per-organization bookmarks, stored only in DRX.
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.core.auth import require_doctor
from app.api.v1.bookmarks import service

router = APIRouter()


class AddBookmarkRequest(BaseModel):
    organization_id: str = Field(..., description="Organization the drug belongs to")
    drug_id: str = Field(..., description="Drug ID from MRX")
    drug_name: str = Field(..., min_length=1, max_length=200, description="Drug name (cached for display)")


@router.post("/drugs", summary="Bookmark a Drug")
async def add_bookmark(request: AddBookmarkRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Doctor bookmarks a drug from an organization for quick access.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "organization_id": "6a5f4fbe...",
      "drug_id": "6a607...",
      "drug_name": "Amlodipine"
    }
    ```

    **Response:**
    ```json
    { "message": "Drug bookmarked", "bookmark_id": "..." }
    ```

    **Rules:**
    - Cannot bookmark same drug twice (per org)
    - Bookmark is per-organization
    """
    return await service.add_bookmark(current_user["_id"], request.organization_id, request.drug_id, request.drug_name)


@router.delete("/drugs/{bookmark_id}", summary="Remove Bookmark")
async def remove_bookmark(bookmark_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove a drug bookmark.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Bookmark removed" }
    ```
    """
    return await service.remove_bookmark(bookmark_id, current_user["_id"])


@router.get("/drugs", summary="My Bookmarked Drugs")
async def get_bookmarks(
    org_id: Optional[str] = Query(None, description="Filter by organization"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get doctor's bookmarked drugs. Optionally filter by organization.

    **Access:** Doctor only

    **Query Params:** `org_id` (optional) — filter to one org's bookmarks

    **Response:**
    ```json
    {
      "total": 3,
      "bookmarks": [
        {
          "id": "...",
          "doctor_id": "...",
          "organization_id": "6a5f4fbe...",
          "drug_id": "6a607...",
          "drug_name": "Amlodipine",
          "bookmarked_at": "2026-07-28T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_bookmarks(current_user["_id"], org_id)


# ══════════════════════════════════════════════════════════════
# CME Event Bookmarks
# ══════════════════════════════════════════════════════════════


class AddCMEBookmarkRequest(BaseModel):
    organization_id: str = Field(..., description="Organization the event belongs to")
    event_id: str = Field(..., description="CME event ID from MRX")
    event_title: str = Field(..., min_length=1, max_length=300, description="Event title (cached)")


@router.post("/cme", summary="Bookmark a CME Event")
async def add_cme_bookmark(request: AddCMEBookmarkRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Doctor bookmarks a CME event for quick access.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "organization_id": "6a5f4fbe...",
      "event_id": "6a605fe9...",
      "event_title": "Cardiology Update 2026"
    }
    ```

    **Response:**
    ```json
    { "message": "CME event bookmarked", "bookmark_id": "..." }
    ```
    """
    return await service.add_cme_bookmark(current_user["_id"], request.organization_id, request.event_id, request.event_title)


@router.delete("/cme/{bookmark_id}", summary="Remove CME Bookmark")
async def remove_cme_bookmark(bookmark_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove a CME event bookmark.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "CME bookmark removed" }
    ```
    """
    return await service.remove_cme_bookmark(bookmark_id, current_user["_id"])


@router.get("/cme", summary="My Bookmarked CME Events")
async def get_cme_bookmarks(
    org_id: Optional[str] = Query(None, description="Filter by organization"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get doctor's bookmarked CME events.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 2,
      "bookmarks": [
        {
          "id": "...",
          "doctor_id": "...",
          "organization_id": "...",
          "event_id": "...",
          "event_title": "Cardiology Update 2026",
          "bookmarked_at": "2026-07-28T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_cme_bookmarks(current_user["_id"], org_id)


# ══════════════════════════════════════════════════════════════
# Post Bookmarks (Feed Posts)
# ══════════════════════════════════════════════════════════════


class AddPostBookmarkRequest(BaseModel):
    post_id: str = Field(..., description="Post ID from DRX feed")
    post_author_name: str = Field(..., min_length=1, max_length=200, description="Author name (cached)")
    post_content_preview: str = Field(default="", max_length=200, description="First 200 chars of content")


@router.post("/posts", summary="Bookmark a Post")
async def add_post_bookmark(request: AddPostBookmarkRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Doctor bookmarks a feed post for quick access later.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "post_id": "6a607...",
      "post_author_name": "Dr. Sneha Reddy",
      "post_content_preview": "New research findings on..."
    }
    ```

    **Response:**
    ```json
    { "message": "Post bookmarked", "bookmark_id": "..." }
    ```

    **Rules:**
    - Cannot bookmark same post twice
    - Post must exist and be active
    """
    return await service.add_post_bookmark(
        current_user["_id"], request.post_id, request.post_author_name, request.post_content_preview
    )


@router.delete("/posts/{bookmark_id}", summary="Remove Post Bookmark")
async def remove_post_bookmark(bookmark_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove a post bookmark.

    **Access:** Doctor only

    **Response:**
    ```json
    { "message": "Post bookmark removed" }
    ```
    """
    return await service.remove_post_bookmark(bookmark_id, current_user["_id"])


@router.get("/posts", summary="My Bookmarked Posts")
async def get_post_bookmarks(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get doctor's bookmarked posts.

    **Access:** Doctor only

    **Response:**
    ```json
    {
      "total": 5,
      "bookmarks": [
        {
          "id": "...",
          "doctor_id": "...",
          "post_id": "...",
          "post_author_name": "Dr. Sneha Reddy",
          "post_content_preview": "New research findings on...",
          "bookmarked_at": "2026-07-28T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_post_bookmarks(current_user["_id"])
