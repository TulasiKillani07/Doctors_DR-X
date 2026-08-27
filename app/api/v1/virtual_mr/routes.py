"""
Virtual MR Routes — Doctor asks AI questions about a drug.

Flow: Doctor → DRX (authz) → MRX (drug + brochure_text) → Groq → answer
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
from app.core.auth import require_doctor
from app.api.v1.virtual_mr import service
from app.api.v1.virtual_mr.schemas import VirtualMRChatRequest, VirtualMRChatResponse

router = APIRouter()
_bearer = HTTPBearer()


@router.post("/chat", response_model=VirtualMRChatResponse, summary="Ask Virtual MR about a Drug")
async def virtual_mr_chat(
    request: VirtualMRChatRequest,
    current_user: Dict = Depends(require_doctor),
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    """
    **Purpose:** Doctor asks an AI question about a specific drug. The AI answers
    strictly from the drug's metadata and official brochure (fetched from the org's MRX).

    **Access:** Doctor only (must be connected to the organization that owns the drug)

    **Flow:**
    ```
    Doctor → DRX (verify doctor↔org) → MRX (drug + brochure_text) → Groq → answer
    ```

    **Request Body:**
    ```json
    {
      "org_id": "6a5f4fbe8498c6a9e9e25038",
      "drug_id": "6a6c7c1637515236e8a95162",
      "question": "What are the main indications for this drug?",
      "history": [
        { "role": "user", "content": "Hi" },
        { "role": "assistant", "content": "Hello, how can I help with this drug?" }
      ]
    }
    ```

    **Response:**
    ```json
    {
      "answer": "This drug is indicated for...",
      "drug_id": "6a6c7c1637515236e8a95162",
      "drug_name": "Atorvastatin",
      "sources": [
        { "type": "drug_metadata", "label": "Drug Information" },
        { "type": "brochure", "label": "Official Brochure" }
      ],
      "used_brochure": true
    }
    ```

    **Notes:**
    - If the drug has no extracted brochure text, the AI uses metadata only and `used_brochure` is false.
    - The AI answers only from provided drug context; it will say when information is unavailable.

    **Errors:**
    - 403: Doctor not connected to the organization
    - 404: Drug not found / not available to this organization
    - 502/503: MRX or AI service unavailable
    """
    return await service.chat(current_user["_id"], credentials.credentials, request)
