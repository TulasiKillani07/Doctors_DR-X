"""
Pydantic models for DRX social features (insert validation).
Used by: notifications, connections, chat, groups, feed
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Notifications ──

class NotificationInDB(BaseModel):
    user_id: str
    title: str
    message: str
    type: str = "general"
    metadata: dict = Field(default_factory=dict)
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


# ── Connections ──

class ConnectionInDB(BaseModel):
    requester_id: str
    receiver_id: str
    requester_name: str = ""
    receiver_name: str = ""
    requester_specialization: Optional[str] = None
    receiver_specialization: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

    class Config:
        extra = "forbid"


# ── Chat ──

class ConversationInDB(BaseModel):
    participants: List[str]
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


class MessageInDB(BaseModel):
    conversation_id: str
    sender_id: str
    content: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


# ── Groups ──

class GroupInDB(BaseModel):
    group_name: str
    group_description: Optional[str] = None
    created_by: str
    admins: List[str] = Field(default_factory=list)
    members: List[str] = Field(default_factory=list)
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


class GroupMessageInDB(BaseModel):
    group_id: str
    sender_id: str
    sender_name: str = ""
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


# ── Feed ──

class PostInDB(BaseModel):
    author_id: str
    author_name: str = ""
    content: str
    image_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


class PostLikeInDB(BaseModel):
    post_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"


class PostCommentInDB(BaseModel):
    post_id: str
    author_id: str
    author_name: str = ""
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "forbid"
