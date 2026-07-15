"""
Service-to-Service Authentication
Completely separate from Doctor/Admin auth.
Used only for integration APIs between DRX and MRX.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.config import settings

service_security = HTTPBearer()

SERVICE_TOKEN_EXPIRE_MINUTES = 15


def create_service_token(organization_id: str, organization_name: str, client_id: str) -> str:
    """Generate a short-lived Service JWT — signed with SERVICE_JWT_SECRET (isolated from user JWTs)"""
    now = datetime.utcnow()
    payload = {
        "organization_id": organization_id,
        "organization_name": organization_name,
        "client_id": client_id,
        "token_type": "service",
        "iat": now,
        "exp": now + timedelta(minutes=SERVICE_TOKEN_EXPIRE_MINUTES)
    }
    return jwt.encode(payload, settings.SERVICE_JWT_SECRET, algorithm=settings.ALGORITHM)


def decode_service_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a Service JWT — uses SERVICE_JWT_SECRET (not SECRET_KEY)"""
    try:
        payload = jwt.decode(token, settings.SERVICE_JWT_SECRET, algorithms=[settings.ALGORITHM])
        if payload.get("token_type") != "service":
            return None
        return payload
    except JWTError:
        return None


async def require_service_auth(
    credentials: HTTPAuthorizationCredentials = Depends(service_security)
) -> Dict[str, Any]:
    """
    Middleware for integration APIs.
    Validates Service JWT only — rejects Doctor/Admin JWTs.
    Attaches organization context to the request.
    """
    token = credentials.credentials
    payload = decode_service_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired service token"
        )

    return {
        "organization_id": payload["organization_id"],
        "organization_name": payload["organization_name"],
        "client_id": payload["client_id"]
    }
