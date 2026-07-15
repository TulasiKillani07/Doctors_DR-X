"""
Doctor Connections service — DRX Doctor Platform
Doctor-to-Doctor connections (professional network)
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


async def send_connection_request(target_doctor_id: str, current_user: Dict) -> Dict[str, str]:
    """Send a connection request to another doctor"""
    db = get_database()
    my_id = current_user["_id"]

    if my_id == target_doctor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect to yourself")

    if not ObjectId.is_valid(target_doctor_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid doctor ID")

    # Check target exists
    target = await db.doctors.find_one({"_id": ObjectId(target_doctor_id)})
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

    # Check if connection already exists (in either direction)
    existing = await db.connections.find_one({
        "$or": [
            {"requester_id": my_id, "receiver_id": target_doctor_id},
            {"requester_id": target_doctor_id, "receiver_id": my_id}
        ]
    })

    if existing:
        s = existing["status"]
        if s == "accepted":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already connected")
        elif s == "pending":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Connection request already pending")
        elif s == "rejected":
            # Allow re-request after rejection
            await db.connections.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "pending", "requester_id": my_id, "receiver_id": target_doctor_id, "updated_at": datetime.utcnow()}}
            )
            return {"message": "Connection request sent"}

    # Create new request
    connection = {
        "requester_id": my_id,
        "receiver_id": target_doctor_id,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    await db.connections.insert_one(connection)
    return {"message": "Connection request sent"}


async def accept_connection(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Accept a pending connection request"""
    db = get_database()

    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection ID")

    connection = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    # Only receiver can accept
    if connection["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the receiver can accept")

    if connection["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connection is already {connection['status']}")

    await db.connections.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {"status": "accepted", "accepted_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
    )

    return {"message": "Connection accepted"}


async def reject_connection(connection_id: str, current_user: Dict) -> Dict[str, str]:
    """Reject a pending connection request"""
    db = get_database()

    if not ObjectId.is_valid(connection_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid connection ID")

    connection = await db.connections.find_one({"_id": ObjectId(connection_id)})
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")

    if connection["receiver_id"] != current_user["_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the receiver can reject")

    if connection["status"] != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Connection is already {connection['status']}")

    await db.connections.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {"status": "rejected", "rejected_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
    )

    return {"message": "Connection rejected"}


async def get_my_connections(current_user: Dict, conn_status: Optional[str] = None) -> Dict[str, Any]:
    """Get doctor's connections"""
    db = get_database()
    my_id = current_user["_id"]

    query = {
        "$or": [
            {"requester_id": my_id},
            {"receiver_id": my_id}
        ]
    }

    if conn_status:
        query["status"] = conn_status

    connections = await db.connections.find(query).sort("updated_at", -1).to_list(length=200)

    results = []
    for conn in connections:
        # Determine the other doctor
        other_id = conn["receiver_id"] if conn["requester_id"] == my_id else conn["requester_id"]
        other_doctor = await db.doctors.find_one(
            {"_id": ObjectId(other_id)},
            {"name": 1, "doctor_gid": 1, "specialization": 1, "hospital": 1, "avatar_url": 1}
        )

        results.append({
            "connection_id": str(conn["_id"]),
            "status": conn["status"],
            "direction": "sent" if conn["requester_id"] == my_id else "received",
            "doctor": {
                "id": other_id,
                "name": other_doctor.get("name", "") if other_doctor else "Unknown",
                "doctor_gid": other_doctor.get("doctor_gid", "") if other_doctor else "",
                "specialization": other_doctor.get("specialization") if other_doctor else None,
                "hospital": other_doctor.get("hospital") if other_doctor else None,
                "avatar_url": other_doctor.get("avatar_url") if other_doctor else None,
            },
            "created_at": conn.get("created_at"),
            "accepted_at": conn.get("accepted_at"),
        })

    return {"total": len(results), "connections": results}


async def get_pending_requests(current_user: Dict) -> Dict[str, Any]:
    """Get pending incoming connection requests"""
    db = get_database()

    connections = await db.connections.find(
        {"receiver_id": current_user["_id"], "status": "pending"}
    ).sort("created_at", -1).to_list(length=100)

    results = []
    for conn in connections:
        requester = await db.doctors.find_one(
            {"_id": ObjectId(conn["requester_id"])},
            {"name": 1, "doctor_gid": 1, "specialization": 1, "hospital": 1, "avatar_url": 1}
        )

        results.append({
            "connection_id": str(conn["_id"]),
            "doctor": {
                "id": conn["requester_id"],
                "name": requester.get("name", "") if requester else "Unknown",
                "doctor_gid": requester.get("doctor_gid", "") if requester else "",
                "specialization": requester.get("specialization") if requester else None,
                "hospital": requester.get("hospital") if requester else None,
                "avatar_url": requester.get("avatar_url") if requester else None,
            },
            "created_at": conn.get("created_at")
        })

    return {"total": len(results), "requests": results}
