"""
Doctor Feed/Posts Routes — DRX Doctor Platform
Professional doctor-to-doctor network posts, likes, comments
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.core.auth import require_doctor
from app.api.v1.feed import service

router = APIRouter()


class CreatePostRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    image_url: Optional[str] = Field(None, max_length=500)


class AddCommentRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class ShareToChatRequest(BaseModel):
    recipient_id: str = Field(..., description="Doctor ID to share with")


@router.post("/posts", summary="Create Post")
async def create_post(request: CreatePostRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Create a new post visible to the doctor's connections.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "content": "Interesting case study on cardiac arrhythmia treatment outcomes...",
      "image_url": "https://cdn.example.com/posts/case-study.jpg"
    }
    ```

    **Response:**
    ```json
    { "message": "Post created", "post_id": "507f1f77bcf86cd799439011" }
    ```

    **Rules:**
    - Content: 1-5000 characters
    - image_url optional (max 500 chars)
    - Post visible to connections + self
    """
    return await service.create_post(request.content, current_user["_id"], current_user.get("name", ""), request.image_url)


@router.get("/feed", summary="Get My Feed")
async def get_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get the doctor's feed — posts from connections and own posts.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 10,
      "posts": [
        {
          "id": "507f1f77bcf86cd799439011",
          "author_id": "...",
          "author_name": "Dr. Arjun Mehta",
          "content": "Interesting case study...",
          "image_url": null,
          "likes_count": 5,
          "comments_count": 2,
          "is_liked": false,
          "is_active": true,
          "created_at": "2026-07-15T10:00:00",
          "updated_at": "2026-07-15T10:00:00"
        }
      ]
    }
    ```

    **`is_liked`:** Whether the current doctor has liked this post.
    """
    return await service.get_feed(current_user["_id"], skip, limit)


@router.post("/posts/{post_id}/like", summary="Like Post")
async def like_post(post_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Like a post.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Post liked" }
    ```

    **Errors:**
    - 400: Already liked
    - 404: Post not found
    """
    return await service.like_post(post_id, current_user["_id"])


@router.delete("/posts/{post_id}/like", summary="Unlike Post")
async def unlike_post(post_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove your like from a post.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Post unliked" }
    ```

    **Errors:**
    - 400: Post not liked by you
    """
    return await service.unlike_post(post_id, current_user["_id"])


@router.post("/posts/{post_id}/comments", summary="Add Comment")
async def add_comment(
    post_id: str, request: AddCommentRequest, current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Add a comment to a post.

    **Access:** Doctor only

    **Request Body:**
    ```json
    { "content": "Great insight! I had a similar case last month." }
    ```

    **Response:**
    ```json
    { "message": "Comment added", "comment_id": "507f1f77bcf86cd799439022" }
    ```

    **Rules:**
    - Content: 1-1000 characters

    **Errors:**
    - 404: Post not found
    """
    return await service.add_comment(post_id, request.content, current_user["_id"], current_user.get("name", ""))


@router.get("/posts/{post_id}/comments", summary="Get Comments")
async def get_comments(
    post_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get all comments on a post.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 5,
      "comments": [
        {
          "id": "...",
          "post_id": "...",
          "author_id": "...",
          "author_name": "Dr. Sneha Reddy",
          "content": "Great insight!",
          "created_at": "2026-07-15T11:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_comments(post_id, skip, limit)


@router.post("/posts/{post_id}/share-to-chat", summary="Share Post to Chat")
async def share_post_to_chat(
    post_id: str,
    request: ShareToChatRequest,
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Share a post to another doctor via direct message.

    **Access:** Doctor only

    **Request Body:**
    ```json
    { "recipient_id": "6a50f173..." }
    ```

    **Response:**
    ```json
    { "message": "Post shared via chat", "conversation_id": "...", "message_id": "..." }
    ```

    **Rules:**
    - Post must exist and be active
    - Recipient must exist
    - Creates/uses existing conversation with recipient
    - Sends formatted message with post preview
    """
    return await service.share_to_chat(post_id, current_user["_id"], request.recipient_id)


@router.get("/posts/me", summary="Get My Posts")
async def get_my_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get only the current doctor's own posts.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 5,
      "posts": [
        {
          "id": "...",
          "author_id": "...",
          "author_name": "Dr. Arjun Mehta",
          "content": "My latest research findings...",
          "image_url": null,
          "likes_count": 3,
          "comments_count": 1,
          "is_liked": false,
          "is_active": true,
          "created_at": "2026-07-28T10:00:00",
          "updated_at": "2026-07-28T10:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_my_posts(current_user["_id"], skip, limit)


@router.delete("/posts/{post_id}", summary="Delete Post")
async def delete_post(post_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Soft-delete your own post. Only the author can delete.

    **Access:** Doctor only (author only)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Post deleted" }
    ```

    **Errors:**
    - 403: Can only delete your own posts
    - 404: Post not found
    """
    return await service.delete_post(post_id, current_user["_id"])
