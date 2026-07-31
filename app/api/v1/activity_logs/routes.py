"""
Activity Logs Routes — DRX Doctor Platform
Per-organization activity logs for drug bookmarks and CME registrations.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Dict, Optional
from bson import ObjectId
from app.core.auth import require_doctor, require_platform_admin
from app.database import get_database

router = APIRouter()


@router.get("/me", summary="Get My Activity Logs")
async def get_my_activity_logs(
    org_id: Optional[str] = Query(None, description="Organization ID (optional — if omitted returns all activity)"),
    action: Optional[str] = Query(None, description="Filter: drug_bookmarked, cme_registered"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Doctor views their activity history (drug bookmarks and CME registrations).

    **Access:** Doctor only

    **Query Params:**
    - `org_id` (optional) — filter by organization
    - `action` (optional) — `drug_bookmarked` or `cme_registered`
    - `skip`, `limit` — pagination

    **Response:**
    ```json
    {
      "total": 5,
      "logs": [
        {
          "id": "6a6aef18...",
          "action": "drug_bookmarked",
          "organization_id": "6a5f4fbe...",
          "metadata": { "drug_id": "6a69e619...", "drug_name": "Amlodipine 5mg" },
          "created_at": "2026-07-30T10:00:00"
        },
        {
          "id": "6a6aef19...",
          "action": "cme_registered",
          "organization_id": "6a5f4fbe...",
          "metadata": { "event_id": "69d4f13f..." },
          "created_at": "2026-07-29T07:56:05"
        }
      ]
    }
    ```

    **Tracked actions:**
    - `drug_bookmarked` — doctor bookmarked a drug
    - `cme_registered` — doctor registered for a CME event
    - `post_created` — doctor created a post
    - `post_liked` — doctor liked a post
    - `comment_posted` — doctor commented on a post
    - `post_bookmarked` — doctor bookmarked a post
    """
    db = get_database()
    doctor_id = current_user["_id"]

    query = {"doctor_id": doctor_id}
    if org_id:
        if not ObjectId.is_valid(org_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")
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
    org_id: str = Query(..., description="Organization ID (required)"),
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

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

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
    org_id: str = Query(..., description="Organization ID (required)"),
    action: Optional[str] = Query(None, description="Filter: drug_bookmarked, cme_registered"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_platform_admin)
):
    """
    **Purpose:** Admin views any doctor's activity logs for a specific organization.

    **Access:** Platform Admin only

    **Query Params:**
    - `org_id` (required) — organization to view logs for
    - `action` (optional) — `drug_bookmarked` or `cme_registered`

    **Response:**
    ```json
    {
      "total": 8,
      "logs": [
        {
          "id": "...",
          "doctor_id": "6a50f173...",
          "action": "drug_bookmarked",
          "organization_id": "6a5f4fbe...",
          "metadata": { "drug_id": "...", "drug_name": "Amlodipine" },
          "created_at": "2026-07-30T10:00:00"
        }
      ]
    }
    ```
    """
    db = get_database()

    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")
    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

    query = {"doctor_id": doctor_id, "organization_id": org_id}
    if action:
        query["action"] = action

    total = await db.activity_logs.count_documents(query)
    logs = await db.activity_logs.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for log in logs:
        log["id"] = str(log.pop("_id"))

    return {"total": total, "logs": logs}
