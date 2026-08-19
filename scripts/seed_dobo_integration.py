"""
One-time script: Insert the DOBO Proxzar integration record into integration_services.
Run from project root: python scripts/seed_dobo_integration.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from datetime import datetime


async def seed():
    from app.database import connect_to_mongo, close_mongo_connection, get_database

    await connect_to_mongo()
    db = get_database()

    # Check if DOBO record already exists
    existing = await db.integration_services.find_one({"service_code": "DOBO"})
    if existing:
        print(f"DOBO record already exists (id={existing['_id']}). Updating to Proxzar model...")
        await db.integration_services.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "authentication_provider": "PROXZAR",
                "proxzar_subject": "rx_integration",
                "proxzar_platform": "dobo",
                "permissions": ["doctor:create"],
                "client_id": None,
                "client_secret_hash": None,
                "updated_at": datetime.utcnow()
            }}
        )
        print("DOBO record updated to Proxzar authentication model.")
    else:
        record = {
            "service_name": "Voice Onboarding (DOBO)",
            "service_code": "DOBO",
            "status": "ACTIVE",
            "description": "Doctor onboarding via voice — authenticates with Proxzar global JWT",
            "authentication_provider": "PROXZAR",
            "proxzar_subject": "rx_integration",
            "proxzar_platform": "dobo",
            "permissions": ["doctor:create"],
            "client_id": None,
            "client_secret_hash": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_used_at": None
        }
        result = await db.integration_services.insert_one(record)
        print(f"DOBO Proxzar integration record created (id={result.inserted_id})")

    # Verify
    dobo = await db.integration_services.find_one({"service_code": "DOBO"})
    print(f"\nVerification:")
    print(f"  service_code: {dobo['service_code']}")
    print(f"  authentication_provider: {dobo['authentication_provider']}")
    print(f"  proxzar_subject: {dobo['proxzar_subject']}")
    print(f"  proxzar_platform: {dobo['proxzar_platform']}")
    print(f"  permissions: {dobo['permissions']}")
    print(f"  status: {dobo['status']}")
    print(f"  client_id: {dobo.get('client_id')} (should be None)")

    await close_mongo_connection()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
