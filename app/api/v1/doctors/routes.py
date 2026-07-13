"""
Doctor Management Routes — Platform Admin only
"""

from fastapi import APIRouter, Depends, UploadFile, File
from app.core.auth import require_platform_admin
from app.api.v1.doctors import service
from app.api.v1.doctors.schemas import BulkUploadResponse

router = APIRouter()


@router.post("/bulk-upload", response_model=BulkUploadResponse, summary="Bulk Upload Doctors")
async def bulk_upload_doctors(
    file: UploadFile = File(..., description="CSV or Excel file"),
    current_user=Depends(require_platform_admin)
):
    """
    **Purpose:** Bulk register doctors from CSV/Excel file. Each doctor gets a unique doctor_gid and default password.

    **Access:** Platform Admin only

    **Required Columns:** name, email, phone

    **Optional Columns:** (ignored if present — profile details are completed by doctor later)

    **CSV Example:**
    ```csv
    name,email,phone
    Dr. Arjun Mehta,arjun@hospital.com,9876543210
    Dr. Sneha Reddy,sneha@clinic.com,9876543211
    Dr. Priya Sharma,priya@hospital.com,9876543212
    ```

    **Response:**
    ```json
    {
      "total_rows": 20,
      "successful": 18,
      "failed": 2,
      "errors": [
        { "row": 5, "email": "duplicate@email.com", "error": "Email already exists" }
      ],
      "message": "Bulk upload completed. 18 doctors added, 2 rows failed."
    }
    ```

    **Rules:**
    - Max 200 rows per upload
    - Max 5MB file size
    - Each doctor gets default password: Welcome@123
    - Each doctor gets unique doctor_gid (PRXDOC + 6 digits)
    - Duplicate email/phone → row skipped with error
    """
    return await service.bulk_upload_doctors(file, current_user)
