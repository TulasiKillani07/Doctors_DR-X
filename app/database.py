"""
MongoDB connection management for DRX Doctor Platform
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from typing import Optional


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


db = Database()


async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.database = db.client[settings.DATABASE_NAME]
    await initialize_collections()


async def close_mongo_connection():
    if db.client:
        db.client.close()


def get_database() -> AsyncIOMotorDatabase:
    return db.database


async def initialize_collections():
    """Create collections and indexes for Doctor Platform"""
    database = get_database()

    # ── admin_users ──
    await database["admin_users"].create_index("email", unique=True, name="admin_email_unique")

    # ── doctors ──
    await database["doctors"].create_index("email", unique=True, name="doctor_email_unique")
    await database["doctors"].create_index("phone", unique=True, name="doctor_phone_unique")
    await database["doctors"].create_index("doctor_gid", unique=True, name="doctor_gid_unique")
    await database["doctors"].create_index("is_active", name="doctor_active_idx")

    # ── organizations ──
    await database["organizations"].create_index("organization_gid", unique=True, name="org_gid_unique")
    await database["organizations"].create_index("organization_name", name="org_name_idx")
    await database["organizations"].create_index("status", name="org_status_idx")

    # ── doctor_organizations ──
    await database["doctor_organizations"].create_index(
        [("doctor_id", 1), ("organization_id", 1)],
        unique=True,
        name="doctor_org_unique"
    )
    await database["doctor_organizations"].create_index("doctor_id", name="doc_org_doctor_idx")
    await database["doctor_organizations"].create_index("organization_id", name="doc_org_org_idx")
    await database["doctor_organizations"].create_index("status", name="doc_org_status_idx")
