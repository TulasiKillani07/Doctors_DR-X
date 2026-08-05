"""
Activity Logs Routes — DRX Doctor Platform
Per-organization activity logs for drug bookmarks and CME registrations.
Social actions use org_id="drx_platform".
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Dict, Optional
from bson import ObjectId
from app.core.auth import require_doctor, require_platform_admin
from app.database import get_database

router = APIRouter()


def _validate_org_id(org_id: str):
    """Allow real org IDs and the special drx_platform sentinel."""
    if org_id != "drx_platform" and not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")


@router.get("/me", summary="Get My Activity Logs")
async def get_my_activity_logs(
    org_id: Optional[str] = Query(None, description="Organization ID or 'drx_platform' for social activity. Omit for all."),
    action: Optional[str] = Query(None, description="Filter: drug_bookmarked, cme_registered, post_created, post_liked, comment_posted, post_bookmarked"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor views their activity history.

    **Access:** Doctor only

    **Query Params:**
    - `org_id` (optional) — use real org ID for drug/CME, `drx_platform` for social, omit for all
    - `action` (optional) — `drug_bookmarked`, `cme_registered`, `post_created`, `post_liked`, `comment_posted`, `post_bookmarked`
    - `skip`, `limit` — pagination

    **Response:**
    ```json
    {
      "total": 5,
      "logs": [
        {
          "id": "...",
          "action": "drug_bookmarked",
          "organization_id": "6a5f4fbe...",
          "metadata": { "drug_id": "...", "drug_name": "Amlodipine 5mg" },
          "created_at": "2026-07-30T10:00:00"
        },
        {
          "id": "...",
          "action": "post_liked",
          "organization_id": "drx_platform",
          "metadata": { "post_id": "..." },
          "created_at": "2026-07-30T12:00:00"
        }
      ]
    }
    ```

    **Tracked actions:**
    - `drug_bookmarked` — doctor bookmarked a drug (org-specific)
    - `cme_registered` — doctor registered for a CME event (org-specific)
    - `post_created` — doctor created a post (org_id=drx_platform)
    - `post_liked` — doctor liked a post (org_id=drx_platform)
    - `comment_posted` — doctor commented on a post (org_id=drx_platform)
    - `post_bookmarked` — doctor bookmarked a post (org_id=drx_platform)
    """
    db = get_database()
    doctor_id = current_user["_id"]

    query = {"doctor_id": doctor_id}
    if org_id:
        _validate_org_id(org_id)
        query["organization_id"] = org_id
    if action:
        query["action"] = action

    total = await db.activity_logs.count_documents(query)
    logs = await db.activity_logs.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for log in logs:
        log["id"] = str(log.pop("_id"))
        log.pop("doctor_id", None)

    return {"total": total, "logs": logs}


@router.get("/stats", summary="My Activity Stats")
async def get_my_activity_stats(
    org_id: str = Query(..., description="Organization ID or 'drx_platform' for social stats"),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get aggregated counts of doctor's activities by action type for an organization.

    **Access:** Doctor only

    **Query Params:** `org_id` (required) — use actual org ID for drug/CME, use `drx_platform` for social

    **Response:**
    ```json
    {
      "organization_id": "6a5f4fbe...",
      "drug_bookmarked": 5,
      "cme_registered": 3,
      "post_created": 10,
      "post_liked": 22,
      "comment_posted": 8,
      "post_bookmarked": 4,
      "total": 52
    }
    ```
    """
    db = get_database()
    doctor_id = current_user["_id"]

    _validate_org_id(org_id)

    pipeline = [
        {"$match": {"doctor_id": doctor_id, "organization_id": org_id}},
        {"$group": {"_id": "$action", "count": {"$sum": 1}}}
    ]

    results = await db.activity_logs.aggregate(pipeline).to_list(length=20)
    stats = {"organization_id": org_id}
    for r in results:
        stats[r["_id"]] = r["count"]
    stats["total"] = sum(v for k, v in stats.items() if k not in ("organization_id",))

    return stats


@router.get("/admin/{doctor_id}", summary="Get Doctor Activity Logs (Admin)")
async def get_doctor_activity_logs(
    doctor_id: str,
    org_id: str = Query(..., description="Organization ID or 'drx_platform'"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_platform_admin)
):
    """
    **Purpose:** Admin views any doctor's activity logs for a specific organization.

    **Access:** Platform Admin only

    **Response:** Same format as /me endpoint.
    """
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")
    _validate_org_id(org_id)

    query = {"doctor_id": doctor_id, "organization_id": org_id}
    if action:
        query["action"] = action

    total = await db.activity_logs.count_documents(query)
    logs = await db.activity_logs.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for log in logs:
        log["id"] = str(log.pop("_id"))

    return {"total": total, "logs": logs}
