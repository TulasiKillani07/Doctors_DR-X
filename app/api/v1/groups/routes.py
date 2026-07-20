"""
Groups Routes — DRX Doctor Platform
Doctor group chats with admin management
"""

from fastapi import APIRouter, Depends, Query
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.auth import require_doctor
from app.api.v1.groups import service

router = APIRouter()


class CreateGroupRequest(BaseModel):
    group_name: str = Field(..., min_length=3, max_length=100)
    group_description: Optional[str] = Field(None, max_length=500)
    member_ids: List[str] = Field(default_factory=list, max_length=49)


class UpdateGroupRequest(BaseModel):
    group_name: Optional[str] = Field(None, min_length=3, max_length=100)
    group_description: Optional[str] = Field(None, max_length=500)


class AddMembersRequest(BaseModel):
    user_ids: List[str] = Field(..., max_length=10)


class GroupMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


@router.post("", summary="Create Group")
async def create_group(request: CreateGroupRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Create a new group chat. Creator becomes admin automatically.

    **Access:** Doctor only

    **Request Body:**
    ```json
    {
      "group_name": "Cardiology Network",
      "group_description": "Discussion for heart specialists",
      "member_ids": ["doctor_id_1", "doctor_id_2"]
    }
    ```

    **Response:**
    ```json
    {
      "group_id": "507f1f77bcf86cd799439011",
      "group_name": "Cardiology Network",
      "members_count": 3,
      "message": "Group created successfully"
    }
    ```

    **Rules:**
    - Group name: 3-100 characters
    - Max 50 members (including creator)
    - Creator is automatically an admin
    """
    return await service.create_group(request.group_name, request.group_description, request.member_ids, current_user)


@router.get("", summary="My Groups")
async def get_my_groups(current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** List all groups where the doctor is a member.

    **Access:** Doctor only

    **Request Body:** None

    **Response:**
    ```json
    {
      "total": 3,
      "groups": [
        {
          "group_id": "...",
          "group_name": "Cardiology Network",
          "group_description": "Heart specialists",
          "members_count": 8,
          "last_message": "See you at the conference!",
          "last_message_at": "2026-07-15T10:00:00",
          "is_admin": true,
          "created_at": "2026-06-01T00:00:00"
        }
      ]
    }
    ```
    """
    return await service.get_my_groups(current_user)


@router.get("/{group_id}", summary="Group Details")
async def get_group(group_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Get detailed group information including all members.

    **Access:** Doctor only (must be a member)

    **Request Body:** None

    **Response:**
    ```json
    {
      "group_id": "...",
      "group_name": "Cardiology Network",
      "group_description": "Heart specialists",
      "created_by": "creator_doctor_id",
      "admins": ["admin_id_1", "admin_id_2"],
      "members": [
        {
          "user_id": "...",
          "name": "Dr. Arjun Mehta",
          "doctor_gid": "PRXDOC482915",
          "specialization": "Cardiology",
          "avatar_url": null,
          "is_admin": true
        }
      ],
      "members_count": 8,
      "created_at": "2026-06-01T00:00:00"
    }
    ```

    **Errors:**
    - 403: Not a member of this group
    - 404: Group not found
    """
    return await service.get_group_details(group_id, current_user)


@router.put("/{group_id}", summary="Update Group (Admin Only)")
async def update_group(group_id: str, request: UpdateGroupRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Update group name and/or description. Only group admins can update.

    **Access:** Doctor only (must be group admin)

    **Request Body:**
    ```json
    {
      "group_name": "Cardiology Specialists",
      "group_description": "Updated description"
    }
    ```

    **Response:**
    ```json
    { "message": "Group updated successfully" }
    ```

    **Errors:**
    - 403: Only admins can update group
    """
    return await service.update_group(group_id, request.group_name, request.group_description, current_user)


@router.post("/{group_id}/members", summary="Add Members (Admin Only)")
async def add_members(group_id: str, request: AddMembersRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Add new members to the group. Only group admins can add.

    **Access:** Doctor only (must be group admin)

    **Request Body:**
    ```json
    { "user_ids": ["doctor_id_1", "doctor_id_2"] }
    ```

    **Response:**
    ```json
    { "message": "Members added", "added": 2 }
    ```

    **Rules:**
    - Max 10 members per request
    - Group limit: 50 members total
    - Cannot add existing members
    """
    return await service.add_members(group_id, request.user_ids, current_user)


@router.delete("/{group_id}/members/{member_id}", summary="Remove Member (Admin Only)")
async def remove_member(group_id: str, member_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Remove a member from the group. Cannot remove the group creator.

    **Access:** Doctor only (must be group admin)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Member removed" }
    ```

    **Errors:**
    - 400: Cannot remove the group creator
    - 403: Only admins can remove members
    """
    return await service.remove_member(group_id, member_id, current_user)


@router.post("/{group_id}/leave", summary="Leave Group")
async def leave_group(group_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Leave a group you're part of.

    **Access:** Doctor only (must be a member)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "You have left the group" }
    ```
    """
    return await service.leave_group(group_id, current_user)


@router.post("/{group_id}/admins/{member_id}", summary="Promote to Admin")
async def make_admin(group_id: str, member_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Promote a group member to admin role.

    **Access:** Doctor only (must be group admin)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Member promoted to admin" }
    ```

    **Errors:**
    - 400: User is not a member / Already an admin
    - 403: Only admins can promote
    """
    return await service.make_admin(group_id, member_id, current_user)


@router.delete("/{group_id}/admins/{admin_id}", summary="Demote Admin")
async def remove_admin(group_id: str, admin_id: str, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Demote an admin back to regular member. Cannot demote the group creator.

    **Access:** Doctor only (must be group admin)

    **Request Body:** None

    **Response:**
    ```json
    { "message": "Admin role removed" }
    ```

    **Errors:**
    - 400: Cannot demote the group creator
    - 403: Only admins can demote
    """
    return await service.remove_admin(group_id, admin_id, current_user)


@router.post("/{group_id}/messages", summary="Send Group Message")
async def send_message(group_id: str, request: GroupMessageRequest, current_user: Dict = Depends(require_doctor)):
    """
    **Purpose:** Send a text message to the group. All members can see it.

    **Access:** Doctor only (must be a group member)

    **Request Body:**
    ```json
    { "content": "Hello everyone! Meeting at 3 PM today." }
    ```

    **Response:**
    ```json
    { "message_id": "507f1f77bcf86cd799439100", "sent_at": "2026-07-15T10:00:00" }
    ```

    **Rules:**
    - Content: 1-2000 characters
    - Only members can send

    **Errors:**
    - 403: Not a member
    """
    return await service.send_group_message(group_id, request.content, current_user)


@router.get("/{group_id}/messages", summary="Get Group Messages")
async def get_messages(
    group_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: Dict = Depends(require_doctor)
):
    """
    **Purpose:** Get message history in a group with pagination.

    **Access:** Doctor only (must be a group member)

    **Request Body:** None

    **Response:**
    ```json
    {
      "messages": [
        {
          "id": "...",
          "group_id": "...",
          "sender_id": "...",
          "sender_name": "Dr. Arjun Mehta",
          "content": "Hello everyone!",
          "created_at": "2026-07-15T10:00:00"
        }
      ],
      "total": 50,
      "page": 1,
      "limit": 50,
      "total_pages": 1
    }
    ```

    **Errors:**
    - 403: Not a member
    """
    return await service.get_group_messages(group_id, current_user, page, limit)
