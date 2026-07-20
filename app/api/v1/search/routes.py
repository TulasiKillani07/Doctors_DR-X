"""
Doctor Search Routes — DRX Doctor Platform
Search doctors for connections, referrals, discovery
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from bson import ObjectId
from app.core.auth import require_doctor
from app.database import get_database

router = APIRouter()


@router.get("/doctors", summary="Search Doctors")
async def search_doctors(
    q: str = Query("", description="Search by name, specialization, hospital, or doctor_gid"),
    city: Optional[str] = Query(None, description="Filter by city"),
    specialization: Optional[str] = Query(None, description="Filter by specialization"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Search doctors on the platform for connections, referrals, or discovery. Shows connection status for each result.

    **Access:** Doctor only

    **Request Body:** None (GET with query params)

    **Query Params:**
    - `q` — text search across name, specialization, hospital, doctor_gid
    - `city` — filter by city
    - `specialization` — filter by specialization
    - `skip` / `limit` — pagination

    **Response:**
    ```json
    {
      "total": 15,
      "doctors": [
        {
          "id": "507f1f77bcf86cd799439011",
          "doctor_gid": "PRXDOC482915",
          "name": "Dr. Arjun Mehta",
          "specialization": "Cardiology",
          "hospital": "Apollo Hospital",
          "city": "Mumbai",
          "avatar_url": null,
          "connection_status": "not_connected",
          "is_connected": false
        },
        {
          "id": "...",
          "doctor_gid": "PRXDOC123456",
          "name": "Dr. Sneha Reddy",
          "specialization": "Neurology",
          "hospital": "Fortis Hospital",
          "city": "Hyderabad",
          "avatar_url": "https://...",
          "connection_status": "accepted",
          "is_connected": true
        }
      ]
    }
    ```

    **Connection Status values:**
    - `not_connected` — no connection exists
    - `pending` — request sent/received
    - `accepted` — connected
    - `rejected` — previously rejected
    - `blocked` — blocked

    **Excludes:** The searching doctor themselves (you won't see yourself in results).
    """
    db = get_database()
    my_id = current_user["_id"]

    query = {"is_active": True, "_id": {"$ne": ObjectId(my_id)}}

    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"specialization": {"$regex": q, "$options": "i"}},
            {"hospital": {"$regex": q, "$options": "i"}},
            {"doctor_gid": {"$regex": q, "$options": "i"}}
        ]

    if city:
        query["city"] = {"$regex": city, "$options": "i"}

    if specialization:
        query["specialization"] = {"$regex": specialization, "$options": "i"}

    total = await db.doctors.count_documents(query)
    doctors = await db.doctors.find(query, {
        "password_hash": 0, "preferences": 0, "locations": 0
    }).sort("name", 1).skip(skip).limit(limit).to_list(length=limit)

    results = []
    for doc in doctors:
        doc_id = str(doc["_id"])
        conn = await db.connections.find_one({
            "$or": [
                {"requester_id": my_id, "receiver_id": doc_id},
                {"requester_id": doc_id, "receiver_id": my_id}
            ]
        })

        connection_status = "not_connected"
        if conn:
            connection_status = conn["status"]

        results.append({
            "id": doc_id,
            "doctor_gid": doc.get("doctor_gid", ""),
            "name": doc.get("name", ""),
            "specialization": doc.get("specialization"),
            "hospital": doc.get("hospital"),
            "city": doc.get("city"),
            "avatar_url": doc.get("avatar_url"),
            "connection_status": connection_status,
            "is_connected": connection_status == "accepted"
        })

    return {"total": total, "doctors": results}
