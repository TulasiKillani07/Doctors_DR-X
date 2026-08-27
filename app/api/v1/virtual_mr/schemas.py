"""
Virtual MR — request/response schemas
"""

from pydantic import BaseModel, Field
from typing import List, Literal


class ChatMessage(BaseModel):
    """A single prior message in the conversation. Only user/assistant roles allowed."""
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class VirtualMRChatRequest(BaseModel):
    org_id: str = Field(..., description="Organization MongoDB _id the doctor is connected to")
    drug_id: str = Field(..., description="Drug ID (owned by the org's MRX)")
    question: str = Field(..., min_length=1, max_length=2000, description="Doctor's question about the drug")
    history: List[ChatMessage] = Field(default_factory=list, max_length=20, description="Prior conversation turns")


class Source(BaseModel):
    type: str = Field(..., description="drug_metadata or brochure")
    label: str


class VirtualMRChatResponse(BaseModel):
    answer: str
    drug_id: str
    drug_name: str
    sources: List[Source]
    used_brochure: bool
