"""
Doctor Chat Routes — DRX Doctor Platform
Doctor-to-Doctor 1:1 messaging
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict
from pydantic import BaseModel, Field
from app.core.auth import require_doctor
from app.api.v1.chat import service

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


@router.get("/conversations", summary="My Conversations (Inbox)")
async def get_conversations(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get all 1:1 chat conversations for the logged-in doctor (inbox view).

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 3,
      "conversations": [
        {
          "conversation_id": "507f1f77bcf86cd799439011",
          "other_doctor": {
            "id": "...",
            "name": "Dr. Sneha Reddy",
            "doctor_gid": "PRXDOC123456",
            "avatar_url": null,
            "specialization": "Neurology"
          },
          "last_message": "Thanks for the referral!",
          "last_message_at": "2026-07-15T10:30:00",
          "unread_count": 2
        }
      ]
    }
    ```
    """
    return await service.get_my_conversations(current_user["_id"])


@router.post("/conversations/{doctor_id}", summary="Start or Get Conversation")
async def start_conversation(doctor_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Start a new conversation with another doctor, or get existing one if it already exists.

    **Access:** Doctor only

    **Request Body:** None (doctor_id in URL path)

    **Response (new):**
    ```json
    {
      "id": "507f1f77bcf86cd799439099",
      "participants": ["your_id", "other_id"],
      "last_message": null,
      "last_message_at": null,
      "created_at": "2026-07-15T10:00:00"
    }
    ```

    **Response (existing):**
    Returns the existing conversation document.

    **Errors:**
    - 400: Cannot chat with yourself
    - 404: Doctor not found
    """
    return await service.get_or_create_conversation(current_user["_id"], doctor_id)


@router.get("/conversations/{conversation_id}/messages", summary="Get Messages")
async def get_messages(
    conversation_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get messages in a conversation. Automatically marks received messages as read.

    **Access:** Doctor only (must be a participant)

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 25,
      "messages": [
        {
          "id": "...",
          "conversation_id": "...",
          "sender_id": "...",
          "content": "Hello Dr. Sneha!",
          "is_read": true,
          "created_at": "2026-07-15T10:00:00"
        }
      ]
    }
    ```

    **Errors:**
    - 403: Not a participant in this conversation
    """
    return await service.get_messages(conversation_id, current_user["_id"], skip, limit)


@router.post("/conversations/{conversation_id}/messages", summary="Send Message")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Send a text message in a conversation.

    **Access:** Doctor only (must be a participant)

    **Request Body:**
    ```json
    { "content": "Hello Dr. Sneha, how are you?" }
    ```

    **Response:**
    ```json
    { "message_id": "507f1f77bcf86cd799439100", "sent_at": "2026-07-15T10:30:00" }
    ```

    **Errors:**
    - 403: Not a participant
    - 404: Conversation not found
    """
    return await service.send_message(conversation_id, current_user["_id"], request.content)


@router.post("/conversations/{conversation_id}/read", summary="Mark All Messages as Read")
async def mark_as_read(
    conversation_id: str,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Mark all unread messages in a conversation as read. Resets unread count badge.

    **Access:** Doctor only (must be a participant)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Messages marked as read", "marked_count": 5 }
    ```

    **Errors:**
    - 403: Not a participant
    """
    return await service.mark_as_read(conversation_id, current_user["_id"])


@router.delete("/messages/{message_id}", summary="Delete Message")
async def delete_message(message_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Delete your own message. Only the sender can delete.

    **Access:** Doctor only (sender only)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Message deleted" }
    ```

    **Errors:**
    - 403: Can only delete your own messages
    - 404: Message not found
    """
    return await service.delete_message(message_id, current_user["_id"])


@router.delete("/conversations/{conversation_id}", summary="Delete Conversation")
async def delete_conversation(conversation_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Delete an entire conversation and all its messages permanently.

    **Access:** Doctor only (must be a participant)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Conversation deleted" }
    ```

    **Errors:**
    - 403: Not a participant
    """
    return await service.delete_conversation(conversation_id, current_user["_id"])
