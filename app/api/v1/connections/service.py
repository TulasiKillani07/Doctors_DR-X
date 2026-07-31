"""
Doctor Connections service — DRX Doctor Platform
Full doctor-to-doctor network: discover, request, accept, reject, cancel, remove, block, unblock
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.models.social_models import ConnectionInDB


async def discover_users(current_user: Dict, search: Optional[str], specialization: Optional[str], page: int, limit: int) -> Dict[str, Any]:
    """Discover doctors to connect with (excludes connected/pending/blocked)"""
    db = get_database()
    my_id = current_user["_id"]

    # Get all connection IDs (any status) to exclude
    connections = await db.connections.find({"$or": [{"requester_id": my_id}, {"receiver_id": my_id}]}).to_list(length=1000)
    excluded_ids = {my_id}
    for conn in connections:
        excluded_ids.add(conn["requester_id"])
        excluded_ids.add(conn["receiver_id"])

    # Build query
    query = {"_id": {"$nin": [ObjectId(uid) for uid in excluded_ids if ObjectId.is_valid(uid)]}, "is_active": True}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if specialization:
        query["specialization"] = {"$regex": specialization, "$options": "i"}

    total = await db.doctors.count_documents(query)
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    skip = (page - 1) * limit

    doctors = await db.doctors.find(query, {"password_hash": 0, "preferences": 0, "locations": 0}).sort("name", 1).skip(skip).limit(limit).to_list(length=limit)

    users = []
    for doc in doctors:
        users.append({
            "user_id": str(doc["_id"]),
            "name": doc.get("name", ""),
            "doctor_gid": doc.get("doctor_gid", ""),
            "specialization": doc.get("specialization"),
            "hospital": doc.get("hospital"),
            "avatar_url": doc.get("avatar_url"),
            "city": doc.get("city")
        })

    return {"users": users, "total": total, "page": page, "limit": limit, "total_pages": total_pages}


async def send_connection_request(receiver_id: str, current_user: Dict) -> Dict[str, Any]:
    """Send a connection request"""
    db = get_database()
    my_id = current_user["_id"]

    if not ObjectId.is_valid(receiver_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")
    if my_id == receiver_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect to yourself")

    receiver = await db.doctors.find_one({"_id": ObjectId(receiver_id)}, {"name": 1, "doctor_gid": 1, "specialization": 1})
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    existing = await db.connections.find_one({"$or": [
        {"requester_id": my_id, "receiver_id": receiver_id},
        {"requester_id": receiver_id, "receiver_id": my_id}
    ]})

    if existing:
        s = existing["status"]
        if s == "accepted":
            raise HTTPException(status_code=400, detail="Already connected")
        elif s == "pending":
            raise HTTPException(status_code=400, detail="Connection request already pending")
        elif s == "blocked":
            raise HTTPException(status_code=400, detail="Cannot send request to this user")
        elif s == "rejected":
            await db.connections.update_one({"_id": existing["_id"]}, {"$set": {"status": "pending", "requester_id": my_id, "receiver_id": receiver_id, "updated_at": datetime.utcnow()}})
            return {"connection_id": str(existing["_id"]), "receiver_name": receiver.get("name", ""), "status": "pending", "message": "Connection request sent"}

    conn = ConnectionInDB(
        requester_id=my_id,
        receiver_id=receiver_id,
        requester_name=current_user.get("name", ""),
        receiver_name=receiver.get("name", ""),
        requester_specialization=current_user.get("specialization"),
        receiver_specialization=receiver.get("specialization"),
        status="pending",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    result = await db.connections.insert_one(conn.model_dump())

    # Notify the receiver about the connection request
    from app.api.v1.notifications.service import create_notification
    await create_notification(
        user_id=receiver_id,
        title="New Connection Request",
        message=f"{current_user.get('name', 'A doctor')} sent you a connection request",
        notification_type="connection_request",
        metadata={"connection_id": str(result.inserted_id), "requester_id": my_id, "requester_name": current_user.get("name", "")}
    )

    return {"connection_id": str(result.inserted_id), "receiver_name": receiver.get("name", ""), "status": "pending", "message": "Connection request sent successfully"}


async def get_received_requests(current_user: Dict, page: int, limit: int) -> Dict[str, Any]:
    """Get pending requests received"""
    db = get_database()
    my_id = current_user["_id"]
    query = {"receiver_id": my_id, "status": "pending"}
    total = await db.connections.count_documents(query)
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    requests = await db.connections.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    results = [{"connection_id": str(r["_id"]), "requester_id": r["requester_id"], "requester_name": r.get("requester_name", ""), "requester_specialization": r.get("requester_specialization"), "status": r["status"], "created_at": r["created_at"]} for r in requests]
    return {"requests": results, "total": total, "page": page, "limit": limit, "total_pages": total_pages}


async def get_sent_requests(current_user: Dict, page: int, limit: int) -> Dict[str, Any]:
    """Get pending requests sent"""
    db = get_database()
    my_id = current_user["_id"]
    query = {"requester_id": my_id, "status": "pending"}
    total = await db.connections.count_documents(query)
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    requests = await db.connections.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    results = [{"connection_id": str(r["_id"]), "receiver_id": r["receiver_id"], "receiver_name": r.get("receiver_name", ""), "receiver_specialization": r.get("receiver_specialization"), "status": r["status"], "created_at": r["created_at"]} for r in requests]
    return {"requests": results, "total": total, "page": page, "limit": limit, "total_pages": total_pages}


async def accept_connection(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Accept a pending connection"""
    db = get_database()
    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    conn = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the receiver can accept")
    if conn["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Connection is already {conn['status']}")
    await db.connections.update_one({"_id": ObjectId(connection_id)}, {"$set": {"status": "accepted", "accepted_at": datetime.utcnow(), "updated_at": datetime.utcnow()}})

    # Notify the requester that their request was accepted
    from app.api.v1.notifications.service import create_notification
    await create_notification(
        user_id=conn["requester_id"],
        title="Connection Accepted",
        message=f"{current_user.get('name', 'A doctor')} accepted your connection request",
        notification_type="connection_accepted",
        metadata={"connection_id": connection_id, "accepter_id": current_user["_id"], "accepter_name": current_user.get("name", "")}
    )

    return {"message": "Connection accepted", "connection_id": connection_id}


async def reject_connection(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Reject a pending connection"""
    db = get_database()
    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    conn = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the receiver can reject")
    if conn["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Connection is already {conn['status']}")
    await db.connections.update_one({"_id": ObjectId(connection_id)}, {"$set": {"status": "rejected", "rejected_at": datetime.utcnow(), "updated_at": datetime.utcnow()}})
    return {"message": "Connection rejected"}


async def cancel_request(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Cancel a sent request"""
    db = get_database()
    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    conn = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn["requester_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the requester can cancel")
    if conn["status"] != "pending":
        raise HTTPException(status_code=400, detail="Can only cancel pending requests")
    await db.connections.delete_one({"_id": ObjectId(connection_id)})
    return {"message": "Connection request cancelled"}


async def get_my_connections(current_user: Dict, conn_status: str, page: int, limit: int) -> Dict[str, Any]:
    """Get connections by status"""
    db = get_database()
    my_id = current_user["_id"]
    query = {"$or": [{"requester_id": my_id}, {"receiver_id": my_id}], "status": conn_status}
    total = await db.connections.count_documents(query)
    skip = (page - 1) * limit
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    connections = await db.connections.find(query).sort("updated_at", -1).skip(skip).limit(limit).to_list(length=limit)

    results = []
    for conn in connections:
        other_id = conn["receiver_id"] if conn["requester_id"] == my_id else conn["requester_id"]
        other = await db.doctors.find_one({"_id": ObjectId(other_id)}, {"name": 1, "doctor_gid": 1, "specialization": 1, "hospital": 1, "avatar_url": 1})
        results.append({
            "connection_id": str(conn["_id"]),
            "user_id": other_id,
            "name": other.get("name", "") if other else "Unknown",
            "doctor_gid": other.get("doctor_gid", "") if other else "",
            "specialization": other.get("specialization") if other else None,
            "hospital": other.get("hospital") if other else None,
            "avatar_url": other.get("avatar_url") if other else None,
            "connected_at": conn.get("accepted_at") or conn.get("updated_at")
        })

    return {"connections": results, "total": total, "page": page, "limit": limit, "total_pages": total_pages}


async def remove_connection(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Remove an accepted connection"""
    db = get_database()
    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=400, detail="Invalid connection ID")
    conn = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    my_id = current_user["_id"]
    if conn["requester_id"] != my_id and conn["receiver_id"] != my_id:
        raise HTTPException(status_code=403, detail="Not your connection")
    if conn["status"] != "accepted":
        raise HTTPException(status_code=400, detail="Connection is not established")
    await db.connections.delete_one({"_id": ObjectId(connection_id)})
    return {"message": "Connection removed successfully"}


async def block_user(doctor_id: str, current_user: Dict) -> Dict[str, str]:
    """Block a doctor"""
    db = get_database()
    my_id = current_user["_id"]
    if not ObjectId.is_valid(doctor_id):
        raise HTTPException(status_code=400, detail="Invalid doctor ID")
    if my_id == doctor_id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    existing = await db.connections.find_one({"$or": [
        {"requester_id": my_id, "receiver_id": doctor_id},
        {"requester_id": doctor_id, "receiver_id": my_id}
    ]})

    if existing:
        await db.connections.update_one({"_id": existing["_id"]}, {"$set": {"status": "blocked", "updated_at": datetime.utcnow()}})
    else:
        block_conn = ConnectionInDB(
            requester_id=my_id,
            receiver_id=doctor_id,
            requester_name=current_user.get("name", ""),
            receiver_name="",
            status="blocked",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        await db.connections.insert_one(block_conn.model_dump())

    return {"message": "User blocked successfully"}


async def unblock_user(doctor_id: str, current_user: Dict) -> Dict[str, str]:
    """Unblock a doctor"""
    db = get_database()
    my_id = current_user["_id"]

    conn = await db.connections.find_one({"$or": [
        {"requester_id": my_id, "receiver_id": doctor_id, "status": "blocked"},
        {"requester_id": doctor_id, "receiver_id": my_id, "status": "blocked"}
    ]})

    if not conn:
        raise HTTPException(status_code=404, detail="No blocked connection found")

    if conn.get("accepted_at"):
        await db.connections.update_one({"_id": conn["_id"]}, {"$set": {"status": "accepted", "updated_at": datetime.utcnow()}})
        return {"message": "User unblocked and connection restored"}
    else:
        await db.connections.delete_one({"_id": conn["_id"]})
        return {"message": "User unblocked successfully"}
