"""
Authentication dependencies for DRX Doctor Platform
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from bson import ObjectId
from app.core.security import decode_access_token
from app.database import get_database

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Get current authenticated user (admin or doctor) from JWT"""
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id: str = payload.get("sub")
    role: str = payload.get("role")

    if not user_id or not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    db = get_database()

    if role == "PLATFORM_ADMIN":
        collection = db["admin_users"]
    elif role == "DOCTOR":
        collection = db["doctors"]
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid role")

    user = await collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")

    user["_id"] = str(user["_id"])
    user["role"] = role
    return user


async def require_platform_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Require PLATFORM_ADMIN role"""
    if current_user.get("role") != "PLATFORM_ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform admin access required")
    return current_user


async def require_doctor(current_user: Dict = Depends(get_current_user)) -> Dict:
    """Require DOCTOR role"""
    if current_user.get("role") != "DOCTOR":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Doctor access required")
    return current_user
