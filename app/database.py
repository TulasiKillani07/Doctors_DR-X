"""
MongoDB connection management for DRX Doctor Platform
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from app.utils.logger import get_drx_logger
from typing import Optional

logger = get_drx_logger("drx.database")


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database: Optional[AsyncIOMotorDatabase] = None


db = Database()


async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGODB_URL)
    db.database = db.client[settings.DATABASE_NAME]
    logger.info(f"Connected to MongoDB: {settings.DATABASE_NAME}")
    await initialize_collections()


async def close_mongo_connection():
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed")


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
    await database["organizations"].create_index("client_id", unique=True, name="org_client_id_unique")
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

    # ── notifications ──
    await database["notifications"].create_index(
        [("user_id", 1), ("created_at", -1)],
        name="notification_user_time_idx"
    )
    await database["notifications"].create_index(
        [("user_id", 1), ("is_read", 1)],
        name="notification_user_read_idx"
    )

    # ── connections ──
    await database["connections"].create_index(
        [("requester_id", 1), ("receiver_id", 1)],
        unique=True,
        name="connection_unique_idx"
    )
    await database["connections"].create_index("requester_id", name="connection_requester_idx")
    await database["connections"].create_index("receiver_id", name="connection_receiver_idx")
    await database["connections"].create_index("status", name="connection_status_idx")

    # ── conversations ──
    await database["conversations"].create_index("participants", name="conv_participants_idx")
    await database["conversations"].create_index("last_message_at", name="conv_last_msg_idx")

    # ── messages ──
    await database["messages"].create_index(
        [("conversation_id", 1), ("created_at", -1)],
        name="msg_conv_time_idx"
    )
    await database["messages"].create_index(
        [("conversation_id", 1), ("is_read", 1)],
        name="msg_conv_read_idx"
    )

    # ── posts ──
    await database["posts"].create_index("author_id", name="post_author_idx")
    await database["posts"].create_index([("is_active", 1), ("created_at", -1)], name="post_active_time_idx")

    # ── post_likes ──
    await database["post_likes"].create_index(
        [("post_id", 1), ("user_id", 1)],
        unique=True,
        name="like_unique_idx"
    )

    # ── post_comments ──
    await database["post_comments"].create_index("post_id", name="comment_post_idx")

    # ── drug_bookmarks ──
    await database["drug_bookmarks"].create_index(
        [("doctor_id", 1), ("organization_id", 1), ("drug_id", 1)],
        unique=True,
        name="bookmark_unique_idx"
    )
    await database["drug_bookmarks"].create_index("doctor_id", name="bookmark_doctor_idx")

    # ── cme_bookmarks ──
    await database["cme_bookmarks"].create_index(
        [("doctor_id", 1), ("organization_id", 1), ("event_id", 1)],
        unique=True,
        name="cme_bookmark_unique_idx"
    )
    await database["cme_bookmarks"].create_index("doctor_id", name="cme_bookmark_doctor_idx")

    # ── post_bookmarks ──
    await database["post_bookmarks"].create_index(
        [("doctor_id", 1), ("post_id", 1)],
        unique=True,
        name="post_bookmark_unique_idx"
    )
    await database["post_bookmarks"].create_index("doctor_id", name="post_bookmark_doctor_idx")

    # ── groups ──
    await database["groups"].create_index("members", name="group_members_idx")
    await database["groups"].create_index("last_message_at", name="group_last_msg_idx")

    # ── group_messages ──
    await database["group_messages"].create_index(
        [("group_id", 1), ("created_at", -1)],
        name="gmsg_group_time_idx"
    )

    # ── activity_logs ──
    await database["activity_logs"].create_index(
        [("doctor_id", 1), ("organization_id", 1), ("created_at", -1)],
        name="activity_doctor_org_time_idx"
    )
    await database["activity_logs"].create_index(
        [("doctor_id", 1), ("organization_id", 1), ("action", 1)],
        name="activity_doctor_org_action_idx"
    )
