"""
Doctor management schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class BulkUploadErrorDetail(BaseModel):
    row: int
    name: Optional[str] = None
    email: Optional[str] = None
    error: str


class BulkUploadResponse(BaseModel):
    total_rows: int
    successful: int
    failed: int
    errors: List[BulkUploadErrorDetail] = []
    message: str
