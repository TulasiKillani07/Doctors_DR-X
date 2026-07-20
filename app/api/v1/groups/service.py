"""
Groups service — DRX Doctor Platform
Doctor group chats (no MRX dependency)
"""

from datetime import datetime
from typing import Dict, Any, List
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


async def create_group(name: str, description: str, member_ids: List[str], current_user: Dict) -> Dict[str, Any]:
    """Create a new group"""
    db = get_database()
    creator_id = current_user["_id"]

    # Validate members exist and are connected
    valid_members = [creator_id]
    for mid in member_ids[:49]:  # Max 50 including creator
        if ObjectId.is_valid(mid) and mid != creator_id:
            doc = await db.doctors.find_one({"_id": ObjectId(mid)}, {"_id": 1})
            if doc:
                valid_members.append(mid)

    group = {
        "group_name": name,
        "group_description": description,
        "created_by": creator_id,
        "admins": [creator_id],
        "members": valid_members,
        "last_message": None,
        "last_message_at": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.groups.insert_one(group)
    return {
        "group_id": str(result.inserted_id),
        "group_name": name,
        "members_count": len(valid_members),
        "message": "Group created successfully"
    }


async def get_my_groups(current_user: Dict) -> Dict[str, Any]:
    """Get all groups where doctor is a member"""
    db = get_database()
    my_id = current_user["_id"]

    groups = await db.groups.find({"members": my_id}).sort("last_message_at", -1).to_list(length=100)

    results = []
    for g in groups:
        results.append({
            "group_id": str(g["_id"]),
            "group_name": g.get("group_name", ""),
            "group_description": g.get("group_description"),
            "members_count": len(g.get("members", [])),
            "last_message": g.get("last_message"),
            "last_message_at": g.get("last_message_at"),
            "is_admin": my_id in g.get("admins", []),
            "created_at": g.get("created_at")
        })

    return {"total": len(results), "groups": results}


async def get_group_details(group_id: str, current_user: Dict) -> Dict[str, Any]:
    """Get group details with member info"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("members", []):
        raise HTTPException(status_code=403, detail="Not a member")

    # Fetch member details
    members = []
    for mid in group.get("members", []):
        doc = await db.doctors.find_one({"_id": ObjectId(mid)}, {"name": 1, "doctor_gid": 1, "specialization": 1, "avatar_url": 1})
        if doc:
            members.append({
                "user_id": mid,
                "name": doc.get("name", ""),
                "doctor_gid": doc.get("doctor_gid", ""),
                "specialization": doc.get("specialization"),
                "avatar_url": doc.get("avatar_url"),
                "is_admin": mid in group.get("admins", [])
            })

    return {
        "group_id": str(group["_id"]),
        "group_name": group.get("group_name", ""),
        "group_description": group.get("group_description"),
        "created_by": group.get("created_by"),
        "admins": group.get("admins", []),
        "members": members,
        "members_count": len(members),
        "created_at": group.get("created_at")
    }


async def update_group(group_id: str, name: str, description: str, current_user: Dict) -> Dict[str, str]:
    """Update group (admin only)"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("admins", []):
        raise HTTPException(status_code=403, detail="Only admins can update group")

    update = {"updated_at": datetime.utcnow()}
    if name:
        update["group_name"] = name
    if description is not None:
        update["group_description"] = description

    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$set": update})
    return {"message": "Group updated successfully"}


async def add_members(group_id: str, user_ids: List[str], current_user: Dict) -> Dict[str, Any]:
    """Add members to group (admin only)"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("admins", []):
        raise HTTPException(status_code=403, detail="Only admins can add members")

    current_members = set(group.get("members", []))
    added = []
    for uid in user_ids[:10]:
        if uid not in current_members and ObjectId.is_valid(uid):
            doc = await db.doctors.find_one({"_id": ObjectId(uid)}, {"_id": 1})
            if doc:
                added.append(uid)

    if added:
        await db.groups.update_one({"_id": ObjectId(group_id)}, {"$push": {"members": {"$each": added}}, "$set": {"updated_at": datetime.utcnow()}})

    return {"message": "Members added", "added": len(added)}


async def remove_member(group_id: str, member_id: str, current_user: Dict) -> Dict[str, str]:
    """Remove member from group (admin only)"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("admins", []):
        raise HTTPException(status_code=403, detail="Only admins can remove members")
    if member_id == group.get("created_by"):
        raise HTTPException(status_code=400, detail="Cannot remove the group creator")

    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$pull": {"members": member_id, "admins": member_id}, "$set": {"updated_at": datetime.utcnow()}})
    return {"message": "Member removed"}


async def leave_group(group_id: str, current_user: Dict) -> Dict[str, str]:
    """Leave a group"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    my_id = current_user["_id"]
    if my_id not in group.get("members", []):
        raise HTTPException(status_code=400, detail="Not a member")

    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$pull": {"members": my_id, "admins": my_id}, "$set": {"updated_at": datetime.utcnow()}})
    return {"message": "You have left the group"}


async def make_admin(group_id: str, member_id: str, current_user: Dict) -> Dict[str, str]:
    """Promote member to admin"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("admins", []):
        raise HTTPException(status_code=403, detail="Only admins can promote members")
    if member_id not in group.get("members", []):
        raise HTTPException(status_code=400, detail="User is not a member")
    if member_id in group.get("admins", []):
        raise HTTPException(status_code=400, detail="Already an admin")

    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$push": {"admins": member_id}})
    return {"message": "Member promoted to admin"}


async def remove_admin(group_id: str, admin_id: str, current_user: Dict) -> Dict[str, str]:
    """Demote admin to member"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("admins", []):
        raise HTTPException(status_code=403, detail="Only admins can demote")
    if admin_id == group.get("created_by"):
        raise HTTPException(status_code=400, detail="Cannot demote the group creator")

    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$pull": {"admins": admin_id}})
    return {"message": "Admin role removed"}


async def send_group_message(group_id: str, content: str, current_user: Dict) -> Dict[str, Any]:
    """Send message to group"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    my_id = current_user["_id"]
    if my_id not in group.get("members", []):
        raise HTTPException(status_code=403, detail="Not a member")

    message = {
        "group_id": group_id,
        "sender_id": my_id,
        "sender_name": current_user.get("name", ""),
        "content": content,
        "created_at": datetime.utcnow()
    }

    result = await db.group_messages.insert_one(message)
    await db.groups.update_one({"_id": ObjectId(group_id)}, {"$set": {"last_message": content[:100], "last_message_at": datetime.utcnow()}})

    return {"message_id": str(result.inserted_id), "sent_at": message["created_at"]}


async def get_group_messages(group_id: str, current_user: Dict, page: int = 1, limit: int = 50) -> Dict[str, Any]:
    """Get messages in a group"""
    db = get_database()
    if not ObjectId.is_valid(group_id):
        raise HTTPException(status_code=400, detail="Invalid group ID")
    group = await db.groups.find_one({"_id": ObjectId(group_id)})
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if current_user["_id"] not in group.get("members", []):
        raise HTTPException(status_code=403, detail="Not a member")

    total = await db.group_messages.count_documents({"group_id": group_id})
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0

    messages = await db.group_messages.find({"group_id": group_id}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    messages.reverse()

    for m in messages:
        m["id"] = str(m.pop("_id"))

    return {"messages": messages, "total": total, "page": page, "limit": limit, "total_pages": total_pages}
