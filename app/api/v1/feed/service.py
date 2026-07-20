"""
Doctor Feed/Posts service — DRX Doctor Platform
Doctor-to-Doctor professional network posts (no MRX dependency)
"""

from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId
from fastapi import HTTPException, status
from app.database import get_database


async def create_post(content: str, doctor_id: str, doctor_name: str, image_url: Optional[str] = None) -> Dict[str, Any]:
    """Doctor creates a post"""
    db = get_database()

    post = {
        "author_id": doctor_id,
        "author_name": doctor_name,
        "content": content,
        "image_url": image_url,
        "likes_count": 0,
        "comments_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.posts.insert_one(post)
    return {"message": "Post created", "post_id": str(result.inserted_id)}


async def get_feed(doctor_id: str, skip: int = 0, limit: int = 20) -> Dict[str, Any]:
    """Get feed — posts from connected doctors + own posts"""
    db = get_database()

    # Get connected doctor IDs
    connections = await db.connections.find(
        {"$or": [{"requester_id": doctor_id}, {"receiver_id": doctor_id}], "status": "accepted"}
    ).to_list(length=500)

    connected_ids = set()
    for conn in connections:
        connected_ids.add(conn["requester_id"])
        connected_ids.add(conn["receiver_id"])
    connected_ids.add(doctor_id)  # Include own posts

    # Fetch posts
    posts = await db.posts.find(
        {"author_id": {"$in": list(connected_ids)}, "is_active": True}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for post in posts:
        post["id"] = str(post.pop("_id"))
        # Check if current doctor liked this post
        liked = await db.post_likes.find_one({"post_id": post["id"], "user_id": doctor_id})
        post["is_liked"] = liked is not None

    return {"total": len(posts), "posts": posts}


async def like_post(post_id: str, doctor_id: str) -> Dict[str, str]:
    """Like a post"""
    db = get_database()

    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": ObjectId(post_id), "is_active": True})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Check if already liked
    existing = await db.post_likes.find_one({"post_id": post_id, "user_id": doctor_id})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already liked")

    await db.post_likes.insert_one({
        "post_id": post_id, "user_id": doctor_id, "created_at": datetime.utcnow()
    })
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {"likes_count": 1}})

    return {"message": "Post liked"}


async def unlike_post(post_id: str, doctor_id: str) -> Dict[str, str]:
    """Unlike a post"""
    db = get_database()

    result = await db.post_likes.delete_one({"post_id": post_id, "user_id": doctor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not liked")

    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {"likes_count": -1}})
    return {"message": "Post unliked"}


async def add_comment(post_id: str, content: str, doctor_id: str, doctor_name: str) -> Dict[str, Any]:
    """Add a comment to a post"""
    db = get_database()

    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": ObjectId(post_id), "is_active": True})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = {
        "post_id": post_id,
        "author_id": doctor_id,
        "author_name": doctor_name,
        "content": content,
        "created_at": datetime.utcnow()
    }

    result = await db.post_comments.insert_one(comment)
    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$inc": {"comments_count": 1}})

    return {"message": "Comment added", "comment_id": str(result.inserted_id)}


async def get_comments(post_id: str, skip: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Get comments for a post"""
    db = get_database()

    comments = await db.post_comments.find(
        {"post_id": post_id}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)

    for c in comments:
        c["id"] = str(c.pop("_id"))

    return {"total": len(comments), "comments": comments}


async def delete_post(post_id: str, doctor_id: str) -> Dict[str, str]:
    """Soft delete a post (only author can delete)"""
    db = get_database()

    if not ObjectId.is_valid(post_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": ObjectId(post_id)})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["author_id"] != doctor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only delete your own posts")

    await db.posts.update_one({"_id": ObjectId(post_id)}, {"$set": {"is_active": False}})
    return {"message": "Post deleted"}
