"""
Authentication dependencies for DRX Doctor Platform

Supports dual-issuer authentication:
- DRX-issued JWT (HS256, verified with SECRET_KEY)
- Proxzar-issued JWT (RS256, verified with Proxzar JWKS public keys)

Both token types resolve to the same DRX user via `sub` (username).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from jose import jwt, JWTError
from app.core.security import decode_access_token
from app.core.proxzar_auth import verify_proxzar_jwt
from app.config import settings
from app.database import get_database
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.auth")

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """
    Get current authenticated user (admin or doctor) from JWT.

    Supports both DRX-issued and Proxzar-issued tokens:
    1. Parse the token payload WITHOUT verification solely to select the verification path.
    2. Route to appropriate verification based on `iss`:
       - "DRX" → HS256 verification with DRX SECRET_KEY
       - "https://oauth2.proxzar.ai" → RS256 verification with Proxzar JWKS
    3. After successful cryptographic verification, trust the payload.
    4. Resolve the DRX user by verified `sub` (username) + `role`.
    """
    token = credentials.credentials

    # ── Step 1: Parse unverified payload ONLY to determine issuer ──
    # This is NOT trusted — it is only used to select which verification path to follow.
    try:
        unverified_payload = jwt.get_unverified_claims(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    candidate_issuer = unverified_payload.get("iss", "")

    # ── Step 2: Verify token cryptographically based on issuer ──
    if candidate_issuer == settings.PROXZAR_ISSUER:
        # Proxzar-issued token → verify with JWKS (RS256)
        # verify_proxzar_jwt handles: signature, iss, aud contains "DRX", exp, kid
        payload = await verify_proxzar_jwt(token)

    elif candidate_issuer == "DRX":
        # DRX-issued token → verify with SECRET_KEY (HS256)
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unrecognized token issuer"
        )

    # ── Step 3: Extract verified claims ──
    username: str = payload.get("sub")
    role: str = payload.get("role")

    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # ── Step 4: Resolve DRX user by username + role ──
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
