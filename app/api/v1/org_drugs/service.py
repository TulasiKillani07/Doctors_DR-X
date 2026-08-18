"""
Organization Drugs service — Doctor views drugs from a connected org's MRX
Flow: Doctor → DRX → mrx_client → MRX → drugs
"""

from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from bson import ObjectId
from app.database import get_database
from app.services.mrx_client import mrx_client, MRXClientError
from app.services.helpers import verify_doctor_org_access


async def list_org_drugs(
    org_id: str,
    doctor_id: str,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Dict[str, Any]:
    """Fetch drugs from an organization's MRX backend"""
    await verify_doctor_org_access(doctor_id, org_id)

    params = {"skip": skip, "limit": limit}
    if search:
        params["search"] = search

    try:
        return await mrx_client.request(org_id, "GET", "/mrx/api/v1/integration/drugs", params=params)
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def get_org_drug_detail(org_id: str, drug_id: str, doctor_id: str, doctor_gid: str = "", doctor_name: str = "") -> Dict[str, Any]:
    """Fetch a single drug detail from an organization's MRX backend and push view event"""
    await verify_doctor_org_access(doctor_id, org_id)

    try:
        result = await mrx_client.request(org_id, "GET", f"/mrx/api/v1/integration/drugs/{drug_id}")
        # Push drug view to MRX (fire-and-forget)
        try:
            await mrx_client.request(org_id, "POST", "/mrx/api/v1/integration/drug-views", body={
                "drug_id": drug_id,
                "drug_name": result.get("drug_name", ""),
                "doctor_gid": doctor_gid,
                "doctor_name": doctor_name
            })
        except Exception:
            pass  # Never block drug detail for analytics
        return result
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)


async def download_org_drug_brochure(org_id: str, drug_id: str, doctor_id: str):
    """Download drug brochure from MRX — streams the PDF back to doctor"""
    from fastapi.responses import StreamingResponse
    import httpx

    await verify_doctor_org_access(doctor_id, org_id)

    # Get the brochure download URL from MRX
    try:
        # First get drug detail to check if brochure exists
        drug = await mrx_client.request(org_id, "GET", f"/mrx/api/v1/integration/drugs/{drug_id}")
        brochure_url = drug.get("brochure_url", "")

        if not brochure_url:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No brochure uploaded for this drug")

        # Stream the PDF from Cloudinary
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(brochure_url)

        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to fetch brochure from storage")

        drug_name = drug.get("drug_name", "drug")
        filename = f"{drug_name}_brochure.pdf".replace(" ", "_")

        return StreamingResponse(
            iter([response.content]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except MRXClientError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=e.message)
