"""
Proxzar Global JWT Authentication — DRX Doctor Platform

Validates JWTs issued by the Proxzar OAuth2 server (https://oauth2.proxzar.ai).
Uses JWKS public keys for local RS256 signature verification.

This is SEPARATE from DRX's own platform login (HS256 + SECRET_KEY).
This is SEPARATE from the old Service JWT (HS256 + SERVICE_JWT_SECRET).

Architecture:
    Proxzar signs JWT with its RSA private key.
    DRX verifies using the corresponding public key from Proxzar's JWKS endpoint.
    No network call to Proxzar per request — keys are cached locally.

Usage:
    from app.core.proxzar_auth import require_proxzar_auth

    @router.post("/endpoint")
    async def my_endpoint(identity: Dict = Depends(require_proxzar_auth)):
        # identity = {"sub": "rx_integration", "role": "admin", "platform": "dobo", ...}
"""

import time
from typing import Dict, Any, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, jwk
from jose.utils import base64url_decode
import httpx
from app.config import settings
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.proxzar_auth")

proxzar_security = HTTPBearer()


# ══════════════════════════════════════════════════════════════
# JWKS Cache
# ══════════════════════════════════════════════════════════════

class JWKSCache:
    """
    In-memory cache for Proxzar's JWKS public keys.

    Refresh strategy:
    - On first request (cold start)
    - When a JWT's `kid` is not found in cache (key rotation)
    - Rate-limited: won't refresh more than once per 60 seconds
    """

    def __init__(self):
        self._keys: Dict[str, Dict] = {}  # kid → JWK dict
        self._last_refresh: float = 0
        self._min_refresh_interval: float = 60  # seconds

    @property
    def is_stale(self) -> bool:
        return not self._keys

    def get_key(self, kid: str) -> Optional[Dict]:
        """Get a cached key by kid."""
        return self._keys.get(kid)

    async def refresh(self) -> None:
        """Fetch JWKS from Proxzar and update cache."""
        now = time.time()

        # Rate limit refreshes
        if now - self._last_refresh < self._min_refresh_interval and self._keys:
            logger.debug("JWKS refresh rate-limited, skipping")
            return

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(settings.PROXZAR_JWKS_URL)

            if response.status_code != 200:
                logger.error(f"JWKS fetch failed: HTTP {response.status_code} from {settings.PROXZAR_JWKS_URL}")
                return

            data = response.json()
            keys = data.get("keys", [])

            if not keys:
                logger.warning("JWKS response contained no keys")
                return

            # Build kid → key map
            new_keys = {}
            for key_data in keys:
                kid = key_data.get("kid")
                if kid:
                    new_keys[kid] = key_data
                else:
                    # Some JWKS have a single key without kid — use "default"
                    new_keys["default"] = key_data

            self._keys = new_keys
            self._last_refresh = now
            logger.info(f"Proxzar JWKS refreshed: {len(new_keys)} key(s) cached")

        except httpx.ConnectError:
            logger.error(f"Cannot connect to Proxzar JWKS: {settings.PROXZAR_JWKS_URL}")
        except httpx.TimeoutException:
            logger.error(f"Proxzar JWKS request timed out: {settings.PROXZAR_JWKS_URL}")
        except Exception as e:
            logger.error(f"JWKS refresh error: {e}")

    async def get_signing_key(self, kid: str) -> Optional[Dict]:
        """
        Get the public key for a given kid.
        If not found, refresh JWKS once (supports key rotation).
        """
        # Cold start
        if self.is_stale:
            await self.refresh()

        key = self.get_key(kid)
        if key:
            return key

        # Try without kid (some JWKS have single key)
        key = self.get_key("default")
        if key:
            return key

        # Kid not found — might be key rotation, refresh once
        logger.info(f"Key kid={kid} not found in cache, refreshing JWKS")
        await self.refresh()

        key = self.get_key(kid)
        if key:
            return key

        return self.get_key("default")


# Singleton cache instance
_jwks_cache = JWKSCache()


# ══════════════════════════════════════════════════════════════
# JWT Verification
# ══════════════════════════════════════════════════════════════

async def verify_proxzar_jwt(token: str) -> Dict[str, Any]:
    """
    Verify a Proxzar-issued JWT.

    Steps:
    1. Read JWT header to get `kid` (key ID)
    2. Fetch matching public key from JWKS cache
    3. Verify RS256 signature
    4. Validate claims: iss, exp, aud

    Returns:
        Decoded JWT payload (all claims)

    Raises:
        HTTPException 401 on any verification failure
    """
    # 1. Extract header without verification to get kid
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format"
        )

    kid = unverified_header.get("kid", "default")
    alg = unverified_header.get("alg", "RS256")

    # 2. Get the signing key from JWKS
    key_data = await _jwks_cache.get_signing_key(kid)
    if not key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find appropriate signing key"
        )

    # 3. Verify signature and decode claims
    try:
        # python-jose handles RS256 verification using the JWK
        # audience can be string or list — python-jose handles both
        payload = jwt.decode(
            token,
            key_data,
            algorithms=[alg, "RS256"],
            audience=settings.PROXZAR_AUDIENCE,
            issuer=settings.PROXZAR_ISSUER
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Proxzar token has expired"
        )
    except jwt.JWTClaimsError as e:
        # Covers: wrong issuer, wrong audience
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token claim validation failed: {str(e)}"
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token signature verification failed: {str(e)}"
        )

    # 4. Additional validation
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim"
        )

    return payload


# ══════════════════════════════════════════════════════════════
# FastAPI Dependency
# ══════════════════════════════════════════════════════════════

async def require_proxzar_auth(
    credentials: HTTPAuthorizationCredentials = Depends(proxzar_security)
) -> Dict[str, Any]:
    """
    FastAPI dependency: Authenticate a Proxzar-issued JWT.

    Verifies:
    - RS256 signature using Proxzar JWKS public key
    - Issuer == PROXZAR_ISSUER
    - Expiry
    - Audience contains PROXZAR_AUDIENCE ("DRX")

    Returns:
        Dict with Proxzar claims: sub, role, platform, iss, aud, exp, etc.
    """
    token = credentials.credentials
    payload = await verify_proxzar_jwt(token)
    return payload
