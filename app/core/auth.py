"""
Authentication dependencies for DRX Doctor Platform

User authentication is via Proxzar-issued JWT only (RS256, verified with Proxzar JWKS).
DRX does not issue its own user tokens.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from app.core.proxzar_auth import verify_proxzar_jwt
from app.database import get_database
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.auth")

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user (admin or doctor) from Proxzar JWT.

    1. Verify token cryptographically using Proxzar JWKS (RS256).
       Validates: signature, iss, aud contains "DRX", exp, kid.
    2. Extract verified `sub` (username) and `role`.
    3. Resolve the DRX user by username + role.

    Does NOT auto-create users. Returns 401 if user not found.
    """
    token = credentials.credentials

    # ── Verify token using Proxzar JWKS ──
    payload = await verify_proxzar_jwt(token)

    # ── Extract verified claims ──
    username: str = payload.get("sub")
    role: str = payload.get("role")

    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # ── Resolve DRX user by username + role ──
    db = get_database()

    if role == "PLATFORM_ADMIN":
        collection = db["admin_users"]
    elif role == "DOCTOR":
        collection = db["doctors"]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid role"
        )

    user = await collection.find_one({"username": username})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account inactive"
        )

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
