"""
MRX Integration Client — Service-to-Service communication with any organization's MRX backend.

This is the reverse equivalent of MRX's drx_client.py.

Architecture:
  DRX talks to MANY organizations. Each org has its own MRX backend.
  Each org has its own cached Service JWT. Tokens are never shared across orgs.

Responsibilities:
  - Read org config from DB (backend_url, integration_client_id, integration_client_secret)
  - Authenticate with the org's MRX
  - Cache Service JWT per organization
  - Refresh expired tokens automatically
  - Make authenticated HTTP requests
  - Handle retries, timeouts, connection failures
  - Return parsed responses

No business logic lives here. This is a pure communication layer.

Usage (by future business services):
    from app.services.mrx_client import mrx_client

    # Generic request — any endpoint, any org
    drugs = await mrx_client.request("org_id_here", "GET", "/api/v1/integration/drugs")
    cme = await mrx_client.request("org_id_here", "GET", "/api/v1/integration/cme")
"""

import time
import logging
from typing import Optional, Dict, Any
import httpx
from bson import ObjectId
from app.database import get_database
from app.config import settings

logger = logging.getLogger("drx.mrx_client")


class MRXClientError(Exception):
    """Raised when MRX client encounters an unrecoverable error."""
    def __init__(self, message: str, status_code: int = 0, org_id: str = ""):
        self.message = message
        self.status_code = status_code
        self.org_id = org_id
        super().__init__(self.message)


class MRXClient:
    """
    Reusable MRX Integration Client.

    Token lifecycle (per organization):
      1. No cached token → request new one from that org's MRX
      2. Token expired → request new one
      3. MRX returns 401 → clear cache, request new one, retry once
      4. Token valid → use it

    Token cache structure:
      _token_cache = {
        "org_id_1": {"token": "eyJ...", "expires_at": 1784020000},
        "org_id_2": {"token": "eyJ...", "expires_at": 1784020500},
      }
    """

    def __init__(self):
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._token_buffer_seconds: int = 60  # Refresh 60s before actual expiry

    # ══════════════════════════════════════════════════════════
    # Organization Lookup
    # ══════════════════════════════════════════════════════════

    async def _get_org_config(self, org_id: str) -> Dict[str, Any]:
        """
        Read organization's integration config from DB.
        Returns: backend_url, integration_client_id, integration_client_secret
        """
        db = get_database()

        if not ObjectId.is_valid(org_id):
            raise MRXClientError("Invalid organization ID", status_code=400, org_id=org_id)

        org = await db.organizations.find_one(
            {"_id": ObjectId(org_id)},
            {
                "organization_name": 1,
                "mrx_url": 1,
                "status": 1
            }
        )

        if not org:
            raise MRXClientError("Organization not found", status_code=404, org_id=org_id)

        if org.get("status") != "ACTIVE":
            raise MRXClientError(
                f"Organization '{org.get('organization_name')}' is inactive",
                status_code=403, org_id=org_id
            )

        mrx_url = org.get("mrx_url")

        if not mrx_url:
            raise MRXClientError(
                f"Organization '{org.get('organization_name')}' is missing mrx_url",
                status_code=503, org_id=org_id
            )

        return {
            "organization_name": org.get("organization_name"),
            "backend_url": mrx_url.rstrip("/"),
            "integration_client_id": settings.DRX_TO_MRX_CLIENT_ID,
            "integration_client_secret": settings.DRX_TO_MRX_SECRET
        }

    # ══════════════════════════════════════════════════════════
    # Token Management (per organization)
    # ══════════════════════════════════════════════════════════

    def _get_cached_token(self, org_id: str) -> Optional[str]:
        """Get cached token for an org if still valid."""
        entry = self._token_cache.get(org_id)
        if not entry:
            return None
        if time.time() >= (entry["expires_at"] - self._token_buffer_seconds):
            return None  # Expired or about to expire
        return entry["token"]

    def _store_token(self, org_id: str, token: str, expires_in: int):
        """Cache a token for an org."""
        self._token_cache[org_id] = {
            "token": token,
            "expires_at": time.time() + expires_in
        }

    def _clear_cache(self, org_id: str):
        """Clear cached token for an org (on 401)."""
        self._token_cache.pop(org_id, None)

    async def _request_new_token(self, org_id: str) -> str:
        """
        Request a new Service JWT from the organization's MRX.
        POST {backend_url}/api/v1/integration/auth/service-token
        """
        config = await self._get_org_config(org_id)
        url = f"{config['backend_url']}/mrx/api/v1/integration/auth/service-token"

        logger.info(f"Requesting Service JWT from MRX | org={config['organization_name']} | url={config['backend_url']}")

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                response = await client.post(url, json={
                    "client_id": config["integration_client_id"],
                    "client_secret": config["integration_client_secret"]
                })
            except httpx.ConnectError:
                raise MRXClientError(
                    f"Cannot connect to MRX at {config['backend_url']} (org: {config['organization_name']})",
                    status_code=503, org_id=org_id
                )
            except httpx.TimeoutException:
                raise MRXClientError(
                    f"MRX token request timed out (org: {config['organization_name']})",
                    status_code=504, org_id=org_id
                )

        if response.status_code == 200:
            data = response.json()
            token = data["access_token"]
            expires_in = data.get("expires_in", 900)
            self._store_token(org_id, token, expires_in)
            logger.info(f"MRX Service JWT obtained | org={config['organization_name']} | expires_in={expires_in}s")
            return token

        elif response.status_code == 401:
            raise MRXClientError(
                f"MRX authentication failed — invalid integration_client_id or integration_client_secret "
                f"(org: {config['organization_name']})",
                status_code=401, org_id=org_id
            )

        elif response.status_code == 403:
            raise MRXClientError(
                f"MRX service client is inactive (org: {config['organization_name']})",
                status_code=403, org_id=org_id
            )

        else:
            raise MRXClientError(
                f"MRX token request failed: {response.status_code} {response.text[:200]} "
                f"(org: {config['organization_name']})",
                status_code=response.status_code, org_id=org_id
            )

    async def _get_token(self, org_id: str) -> str:
        """Get a valid token for an org — cached or fresh."""
        cached = self._get_cached_token(org_id)
        if cached:
            logger.debug(f"Using cached MRX token | org_id={org_id}")
            return cached
        return await self._request_new_token(org_id)

    # ══════════════════════════════════════════════════════════
    # Generic Request Method
    # ══════════════════════════════════════════════════════════

    async def request(
        self,
        org_id: str,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
        retry_on_401: bool = True
    ) -> Dict[str, Any]:
        """
        Send an authenticated request to an organization's MRX backend.

        Args:
            org_id: Organization MongoDB _id
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API path (e.g. "/api/v1/integration/drugs")
            params: Query parameters
            body: JSON body
            retry_on_401: Whether to retry once on 401 (default True)

        Returns:
            Parsed JSON response from MRX

        Raises:
            MRXClientError: On authentication, connection, or HTTP errors
        """
        config = await self._get_org_config(org_id)
        token = await self._get_token(org_id)
        url = f"{config['backend_url']}{endpoint}"
        headers = {"Authorization": f"Bearer {token}"}

        logger.info(f"Calling MRX {method} {endpoint} | org={config['organization_name']}")

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=body
                )
            except httpx.ConnectError:
                raise MRXClientError(
                    f"Cannot connect to MRX at {url} (org: {config['organization_name']})",
                    status_code=503, org_id=org_id
                )
            except httpx.TimeoutException:
                raise MRXClientError(
                    f"MRX request timed out: {method} {endpoint} (org: {config['organization_name']})",
                    status_code=504, org_id=org_id
                )

        # Handle 401 — token might have expired
        if response.status_code == 401 and retry_on_401:
            logger.warning(f"MRX returned 401 — refreshing token | org={config['organization_name']}")
            self._clear_cache(org_id)
            return await self.request(org_id, method, endpoint, params, body, retry_on_401=False)

        # Handle other errors
        if response.status_code == 403:
            raise MRXClientError(
                f"MRX forbidden: {response.text[:200]} (org: {config['organization_name']})",
                status_code=403, org_id=org_id
            )

        if response.status_code == 404:
            raise MRXClientError(
                f"MRX resource not found: {method} {endpoint} (org: {config['organization_name']})",
                status_code=404, org_id=org_id
            )

        if response.status_code >= 500:
            raise MRXClientError(
                f"MRX server error: {response.status_code} {response.text[:200]} (org: {config['organization_name']})",
                status_code=response.status_code, org_id=org_id
            )

        if response.status_code >= 400:
            raise MRXClientError(
                f"MRX error: {response.status_code} {response.text[:200]} (org: {config['organization_name']})",
                status_code=response.status_code, org_id=org_id
            )

        return response.json()

    # ══════════════════════════════════════════════════════════
    # Health Check (utility)
    # ══════════════════════════════════════════════════════════

    async def health_check(self, org_id: str) -> Dict[str, Any]:
        """
        Verify DRX can authenticate with a specific org's MRX.
        Does NOT call any business endpoint — just validates token exchange.
        """
        try:
            config = await self._get_org_config(org_id)
            await self._get_token(org_id)
            return {
                "status": "ok",
                "organization_name": config["organization_name"],
                "backend_url": config["backend_url"],
                "token_valid": True
            }
        except MRXClientError as e:
            return {
                "status": "error",
                "org_id": org_id,
                "message": e.message,
                "status_code": e.status_code
            }


# ══════════════════════════════════════════════════════════════
# Singleton instance — import this throughout DRX
# ══════════════════════════════════════════════════════════════
mrx_client = MRXClient()
