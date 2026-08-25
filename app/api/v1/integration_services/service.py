"""
Integration Services — Business Logic
Manages trusted integration service records (DOBO, etc.)
Authentication is via Proxzar JWT. This module manages authorization (permissions).
"""

from datetime import datetime
from typing import Dict, Any
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database
from app.models.integration_service_model import IntegrationServiceInDB


async def create_service(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new integration service."""
    db = get_database()

    service_name = data["service_name"]
    service_code = data["service_code"].upper()
    description = data.get("description")

    # Check duplicate service_code
    existing = await db.integration_services.find_one({"service_code": service_code})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Service with code '{service_code}' already exists")

    # Create document
    service_doc = IntegrationServiceInDB(
        service_name=service_name,
        service_code=service_code,
        status="ACTIVE",
        description=description,
        authentication_provider="PROXZAR",
        proxzar_subject=data.get("proxzar_subject"),
        proxzar_platform=data.get("proxzar_platform"),
        permissions=data.get("permissions", []),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_used_at=None
    )

    result = await db.integration_services.insert_one(service_doc.model_dump())

    return {
        "message": "Integration service created successfully",
        "service_id": str(result.inserted_id),
        "service_name": service_name,
        "service_code": service_code,
        "status": "ACTIVE"
    }


async def get_all_services() -> Dict[str, Any]:
    """List all integration services"""
    db = get_database()

    services = await db.integration_services.find({}).sort("created_at", -1).to_list(length=100)

    results = []
    for svc in services:
        results.append({
            "id": str(svc["_id"]),
            "service_name": svc["service_name"],
            "service_code": svc["service_code"],
            "status": svc["status"],
            "description": svc.get("description"),
            "authentication_provider": svc.get("authentication_provider", "PROXZAR"),
            "proxzar_subject": svc.get("proxzar_subject"),
            "proxzar_platform": svc.get("proxzar_platform"),
            "permissions": svc.get("permissions", []),
            "created_at": svc["created_at"],
            "updated_at": svc["updated_at"],
            "last_used_at": svc.get("last_used_at")
        })

    return {"total": len(results), "services": results}


async def set_status(service_id: str, new_status: str) -> Dict[str, str]:
    """Activate or deactivate a service"""
    db = get_database()

    if not ObjectId.is_valid(service_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid service ID")
    if new_status not in ("ACTIVE", "INACTIVE"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status must be ACTIVE or INACTIVE")

    result = await db.integration_services.update_one(
        {"_id": ObjectId(service_id)},
        {"$set": {"status": new_status, "updated_at": datetime.utcnow()}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    return {"message": f"Service {'activated' if new_status == 'ACTIVE' else 'deactivated'} successfully"}


async def update_last_used(client_id: str):
    """Update last_used_at timestamp. Called on every successful authentication."""
    db = get_database()
    await db.integration_services.update_one(
        {"client_id": client_id},
        {"$set": {"last_used_at": datetime.utcnow()}}
    )
