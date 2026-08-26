"""
Log Viewer API — View server logs from the drx.log file.
Access: Platform Admin only.
"""

from fastapi import APIRouter, Query, Depends
from fastapi.responses import PlainTextResponse
from pathlib import Path
from app.config import settings
from app.core.auth import require_platform_admin

router = APIRouter()


@router.get("/logs", response_class=PlainTextResponse, summary="View Server Logs (Admin)")
async def get_logs(
    lines: int = Query(100, ge=1, le=5000, description="Number of lines to return (from end)"),
    search: str = Query(None, description="Filter lines containing this text"),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** View the last N lines of the DRX server log file.

    **Access:** Public (no auth — use for debugging only, disable in production)

    **Query Params:**
    - `lines` — number of lines from end (default 100, max 5000)
    - `search` — filter lines containing this text

    **Example:**
    ```
    GET /drxdb/logs?lines=50
    GET /drxdb/logs?lines=200&search=auto-link
    GET /drxdb/logs?search=ERROR
    ```
    """
    log_file = Path(settings.LOG_DIR) / "drx.log"

    if not log_file.exists():
        return f"Log file not found at: {log_file}"

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return f"Error reading log file: {e}"

    # Get last N lines
    tail_lines = all_lines[-lines:]

    # Filter if search provided
    if search:
        tail_lines = [line for line in tail_lines if search.lower() in line.lower()]

    if not tail_lines:
        return "No matching log entries found."

    return "".join(tail_lines)
