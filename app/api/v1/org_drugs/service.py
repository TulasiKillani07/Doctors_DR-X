"""
Organization Drugs service — Doctor views drugs from a connected org's MRX
Flow: Doctor → DRX → mrx_client → MRX → drugs
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.services.mrx_client import mrx_client, MRXClientError


async def _verify_doctor_org_access(doctor_id: str, org_id: str):
    """Verify the doctor has an ACTIVE relationship with this org"""
    db = get_database()

    if not ObjectId.is_valid(org_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid organization ID")

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


async def list_org_drugs(
    org_id: str,
    doctor_id: str,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """Fetch drugs from an organization's MRX backend"""
    await _verify_doctor_org_access(doctor_id, org_id)

    params = {"skip": skip, "limit": limit}
    if search:
        params["search"] = search

    try:
        return await mrx_client.request(org_id, "GET", "/api/v1/integration/drugs", params=params)
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def get_org_drug_detail(org_id: str, drug_id: str, doctor_id: str) -> Dict[str, Any]:
    """Fetch a single drug detail from an organization's MRX backend"""
    await _verify_doctor_org_access(doctor_id, org_id)

    try:
        return await mrx_client.request(org_id, "GET", f"/api/v1/integration/drugs/{drug_id}")
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
