"""
Doctor Chat service — DRX Doctor Platform
Doctor-to-Doctor messaging (no MRX dependency)
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.models.social_models import ConversationInDB, MessageInDB


async def get_or_create_conversation(doctor_id: str, other_doctor_id: str) -> Dict[str, Any]:
    """Get existing conversation or create new one between two doctors"""
    db = get_database()

    if doctor_id == other_doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot chat with yourself")

    if not ObjectId.is_valid(other_doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    # Check other doctor exists
    other = await db.doctors.find_one({"_id": ObjectId(other_doctor_id)}, {"name": 1})
    if not other:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # Find existing conversation (participants in any order)
    participants = sorted([doctor_id, other_doctor_id])
    conversation = await db.conversations.find_one({"participants": participants})

    if conversation:
        conversation["id"] = str(conversation.pop("_id"))
        return conversation

    # Create new
    conv = ConversationInDB(
        participants=participants,
        last_message=None,
        last_message_at=None,
        created_at=datetime.utcnow()
    )
    result = await db.conversations.insert_one(conv.model_dump())
    conv = conv.model_dump()
    conv["id"] = str(result.inserted_id)
    conv.pop("_id", None)
    return conv


async def get_my_conversations(doctor_id: str) -> Dict[str, Any]:
    """Get all conversations for a doctor"""
    db = get_database()

    conversations = await db.conversations.find(
        {"participants": doctor_id}
    ).sort("last_message_at", -1).to_list(length=100)

    if not conversations:
        return {"total": 0, "conversations": []}

    # Collect all "other" participant IDs
    other_ids = []
    for conv in conversations:
        other_id = [p for p in conv["participants"] if p != doctor_id][0]
        other_ids.append(other_id)

    # Batch fetch all other doctors in one query
    other_oids = [ObjectId(uid) for uid in other_ids if ObjectId.is_valid(uid)]
    doctors_list = await db.doctors.find(
        {"_id": {"$in": other_oids}},
        {"name": 1, "doctor_gid": 1, "avatar_url": 1, "specialization": 1}
    ).to_list(length=len(other_oids))
    doctor_map = {str(doc["_id"]): doc for doc in doctors_list}

    # Batch count unread messages per conversation
    conv_ids = [str(conv["_id"]) for conv in conversations]
    unread_pipeline = [
        {"$match": {"conversation_id": {"$in": conv_ids}, "sender_id": {"$ne": doctor_id}, "is_read": False}},
        {"$group": {"_id": "$conversation_id", "count": {"$sum": 1}}}
    ]
    unread_results = await db.messages.aggregate(unread_pipeline).to_list(length=len(conv_ids))
    unread_map = {r["_id"]: r["count"] for r in unread_results}

    results = []
    for conv, other_id in zip(conversations, other_ids):
        other = doctor_map.get(other_id)
        conv_id = str(conv["_id"])

        results.append({
            "conversation_id": conv_id,
            "other_doctor": {
                "id": other_id,
                "name": other.get("name", "") if other else "Unknown",
                "doctor_gid": other.get("doctor_gid", "") if other else "",
                "avatar_url": other.get("avatar_url") if other else None,
                "specialization": other.get("specialization") if other else None,
            },
            "last_message": conv.get("last_message"),
            "last_message_at": conv.get("last_message_at"),
            "unread_count": unread_map.get(conv_id, 0)
        })

    return {"total": len(results), "conversations": results}


async def send_message(conversation_id: str, sender_id: str, content: str) -> Dict[str, Any]:
    """Send a message in a conversation"""
    db = get_database()

    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    # Verify sender is in conversation
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if sender_id not in conv["participants"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")

    message = MessageInDB(
        conversation_id=conversation_id,
        sender_id=sender_id,
        content=content,
        is_read=False,
        created_at=datetime.utcnow()
    )

    result = await db.messages.insert_one(message.model_dump())

    # Update conversation
    await db.conversations.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"last_message": content[:100], "last_message_at": datetime.utcnow()}}
    )

    return {"message_id": str(result.inserted_id), "sent_at": message.created_at}


async def get_messages(conversation_id: str, doctor_id: str, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Get messages in a conversation"""
    db = get_database()

    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    # Verify participant
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv or doctor_id not in conv["participants"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")

    messages = await db.messages.find(
        {"conversation_id": conversation_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    # Mark messages from other person as read
    await db.messages.update_many(
        {"conversation_id": conversation_id, "sender_id": {"$ne": doctor_id}, "is_read": False},
        {"$set": {"is_read": True}}
    )

    for m in messages:
        m["id"] = str(m.pop("_id"))

    return {"total": len(messages), "messages": messages}



async def mark_as_read(conversation_id: str, doctor_id: str) -> Dict[str, Any]:
    """Mark all messages in conversation as read"""
    db = get_database()

    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv or doctor_id not in conv["participants"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")

    result = await db.messages.update_many(
        {"conversation_id": conversation_id, "sender_id": {"$ne": doctor_id}, "is_read": False},
        {"$set": {"is_read": True}}
    )

    return {"message": "Messages marked as read", "marked_count": result.modified_count}


async def delete_message(message_id: str, doctor_id: str) -> Dict[str, str]:
    """Delete own message and update conversation's last_message if needed"""
    db = get_database()

    if not ObjectId.is_valid(message_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID")

    msg = await db.messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg["sender_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only delete your own messages")

    conversation_id = msg["conversation_id"]

    # Delete the message
    await db.messages.delete_one({"_id": ObjectId(message_id)})

    # Check if this was the conversation's last_message — if so, recalculate
    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if conv and conv.get("last_message") == msg.get("content", "")[:100]:
        # Find the new last message
        new_last = await db.messages.find_one(
            {"conversation_id": conversation_id},
            sort=[("created_at", -1)]
        )
        await db.conversations.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$set": {
                "last_message": new_last["content"][:100] if new_last else None,
                "last_message_at": new_last["created_at"] if new_last else None
            }}
        )

    return {"message": "Message deleted"}


async def delete_conversation(conversation_id: str, doctor_id: str) -> Dict[str, str]:
    """Delete conversation and all its messages"""
    db = get_database()

    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    conv = await db.conversations.find_one({"_id": ObjectId(conversation_id)})
    if not conv or doctor_id not in conv["participants"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")

    await db.messages.delete_many({"conversation_id": conversation_id})
    await db.conversations.delete_one({"_id": ObjectId(conversation_id)})
    return {"message": "Conversation deleted"}
