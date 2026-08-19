"""
Organization Drugs Routes — Doctor views drugs from connected org's MRX
"""

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Optional
from app.core.auth import require_doctor
from app.api.v1.org_drugs import service

router = APIRouter()
_bearer = HTTPBearer()


@router.get("/{org_id}/drugs", summary="List Organization Drugs")
async def list_drugs(
    org_id: str,
    search: Optional[str] = Query(None, description="Search by drug name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor views drugs from one of their connected organizations.

    **Access:** Doctor only (must be connected to the organization)

    **Flow:**
    ```
    Doctor → Proxzar JWT → DRX → forwards same JWT → MRX /integration/drugs → response
    ```

    **Query Params:** `search`, `skip`, `limit`

    **Response:**
    ```json
    {
      "total": 45,
      "drugs": [
        {
          "drug_name": "Amlodipine",
          "generic_name": "Amlodipine Besylate",
          "therapeutic_category": "Cardiovascular",
          "dosage_form": "Tablet",
          "strength": "5mg",
          "packaging": { ... },
          "brochure_url": "https://..."
        }
      ],
      "organization": "XYZ Pharma Pvt Ltd"
    }
    ```

    **Errors:**
    - 403: Doctor not connected to this organization
    - 502: MRX backend unreachable or returned error
    """
    return await service.list_org_drugs(org_id, current_user["_id"], credentials.credentials, search, skip, limit)


@router.get("/{org_id}/drugs/{drug_id}", summary="Get Drug Detail")
async def get_drug_detail(
    org_id: str,
    drug_id: str,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Doctor views a single drug's full detail from a connected organization.

    **Access:** Doctor only (must be connected to the organization)

    **Flow:**
    ```
    Doctor → Proxzar JWT → DRX → forwards same JWT → MRX /integration/drugs/{drug_id} → response
    ```

    **Response:** Full drug document with packaging info.

    **Errors:**
    - 403: Doctor not connected to this organization
    - 404: Drug not found on MRX
    - 502: MRX backend unreachable
    """
    return await service.get_org_drug_detail(org_id, drug_id, current_user["_id"], credentials.credentials, current_user.get("doctor_gid", ""), current_user.get("name", ""))


@router.get("/{org_id}/drugs/{drug_id}/brochure/download", summary="Download Drug Brochure")
async def download_drug_brochure(
    org_id: str,
    drug_id: str,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer)
):
    """
    **Purpose:** Download drug brochure PDF from the connected organization's MRX.

    **Access:** Doctor only (must be connected to the organization)

    **Flow:**
    ```
    Doctor → Proxzar JWT → DRX → forwards same JWT → MRX /drugs/{drug_id}/brochure/download → PDF stream
    ```

    **Response:** PDF file streamed with download headers.

    **Errors:**
    - 403: Not connected to org
    - 404: Drug not found or no brochure uploaded
    - 502: MRX unreachable
    """
    return await service.download_org_drug_brochure(org_id, drug_id, current_user["_id"], credentials.credentials)
