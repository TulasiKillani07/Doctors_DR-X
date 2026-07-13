"""
Doctor management service — bulk upload
"""

import re
from datetime import datetime
from typing import Dict, Any
from fastapi import HTTPException, UploadFile
import pandas as pd
from io import BytesIO
from app.database import get_database
from app.core.security import hash_password
from app.config import settings
from app.models.doctor_model import DoctorInDB, generate_doctor_gid


def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    cleaned = re.sub(r'[^0-9]', '', str(phone))
    return len(cleaned) == 10


async def bulk_upload_doctors(file: UploadFile, admin_user: Dict) -> Dict[str, Any]:
    """Bulk upload doctors from CSV"""
    db = get_database()

    # Validate file type
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files supported")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")

    # Parse file
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    # Clean column names
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]

    # Validate required columns
    required = ["name", "email", "phone"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing)}")

    if len(df) > 200:
        raise HTTPException(status_code=400, detail=f"Max 200 rows per upload. File has {len(df)} rows.")

    successful = 0
    failed = 0
    errors = []

    for idx, row in df.iterrows():
        row_number = idx + 2  # 1-indexed + header

        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
        email = str(row.get('email', '')).strip().lower() if pd.notna(row.get('email')) else ''
        phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''

        # Validate
        if not name:
            errors.append({"row": row_number, "email": email, "error": "Name is required"})
            failed += 1
            continue

        if not email or not validate_email(email):
            errors.append({"row": row_number, "name": name, "error": "Invalid or missing email"})
            failed += 1
            continue

        # Clean phone
        phone_cleaned = re.sub(r'[^0-9]', '', phone)
        if len(phone_cleaned) > 10:
            phone_cleaned = phone_cleaned[-10:]

        if not validate_phone(phone_cleaned):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Phone must be 10 digits"})
            failed += 1
            continue

        # Check duplicates in DB
        if await db.doctors.find_one({"email": email}):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Email already exists"})
            failed += 1
            continue

        if await db.doctors.find_one({"phone": phone_cleaned}):
            errors.append({"row": row_number, "name": name, "email": email, "error": "Phone already exists"})
            failed += 1
            continue

        # Generate unique GID
        doctor_gid = generate_doctor_gid()
        while await db.doctors.find_one({"doctor_gid": doctor_gid}):
            doctor_gid = generate_doctor_gid()

        # Create doctor
        try:
            doctor = DoctorInDB(
                doctor_gid=doctor_gid,
                email=email,
                phone=phone_cleaned,
                password_hash=hash_password(settings.DEFAULT_USER_PASSWORD),
                name=name,
                is_active=True,
                is_email_verified=False,
                is_phone_verified=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            await db.doctors.insert_one(doctor.model_dump())
            successful += 1
        except Exception as e:
            errors.append({"row": row_number, "name": name, "email": email, "error": f"DB error: {str(e)}"})
            failed += 1

    message = f"Bulk upload completed. {successful} doctors added"
    if failed > 0:
        message += f", {failed} rows failed."
    else:
        message += " successfully."

    return {
        "total_rows": len(df),
        "successful": successful,
        "failed": failed,
        "errors": errors,
        "message": message
    }
