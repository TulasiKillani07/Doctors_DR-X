"""
Activity Logger — DRX Doctor Platform

Tracks doctor actions per organization for analytics and engagement metrics.
Fire-and-forget: logging failures never break the main flow.

Usage:
    from app.services.activity_logger import log_activity

    await log_activity(doctor_id, org_id, "drug_viewed", {"drug_id": "...", "drug_name": "..."})
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.database import get_database
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.activity_logger")


# ══════════════════════════════════════════════════════════════
# Pydantic Model — DB Write Validation
# ══════════════════════════════════════════════════════════════

class ActivityLogInDB(BaseModel):
    """Write model for activity_logs collection"""
    model_config = ConfigDict(extra="forbid")

    doctor_id: str
    organization_id: str
    action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════
# Valid Actions
# ══════════════════════════════════════════════════════════════

VALID_ACTIONS = {
    "drug_bookmarked",
    "cme_registered",
    "post_bookmarked",
    "post_liked",
    "comment_posted",
    "post_created",
}


# ══════════════════════════════════════════════════════════════
# Log Function (fire-and-forget)
# ══════════════════════════════════════════════════════════════

async def log_activity(
    doctor_id: str,
    organization_id: str,
    action: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a doctor activity per organization. Never raises — failures are logged and swallowed.

    Args:
        doctor_id: Doctor's string ID
        organization_id: Organization ID this activity belongs to
        action: One of VALID_ACTIONS
        metadata: Extra context (drug_id, post_id, event_id, etc.)
    """
    if action not in VALID_ACTIONS:
        logger.warning(f"Unknown activity action: {action}")
        return

    try:
        db = get_database()
        entry = ActivityLogInDB(
            doctor_id=doctor_id,
            organization_id=organization_id,
            action=action,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        await db.activity_logs.insert_one(entry.model_dump())
    except Exception as e:
        logger.error(f"Failed to log activity: {action} for doctor {doctor_id} org {organization_id} — {e}")
