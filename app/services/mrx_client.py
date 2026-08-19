"""
MRX Integration Client — Token-forwarding architecture.

DRX forwards the user's Proxzar JWT to MRX.
MRX independently verifies the Proxzar token using JWKS.

There is no:
- client_id / client_secret exchange
- Service JWT
- Token cache
- Token refresh/retry on 401

If MRX returns 401, DRX propagates it — the user must re-authenticate via Proxzar.

Responsibilities:
  - Read org config from DB (mrx_url)
  - Forward the user's Proxzar JWT as Authorization header
  - Make authenticated HTTP requests
  - Handle timeouts, connection failures
  - Return parsed responses

Usage:
    from app.services.mrx_client import mrx_client

    drugs = await mrx_client.request(org_id, "GET", "/api/v1/integration/drugs", token=user_token)
"""

from typing import Optional, Dict, Any
import httpx
from bson import ObjectId
from app.database import get_database
from app.utils.logger import get_drx_logger

logger = get_drx_logger("drx.mrx_client")


class MRXClientError(Exception):
    """Raised when MRX client encounters an unrecoverable error."""
    def __init__(self, message: str, status_code: int = 0, org_id: str = ""):
        self.message = message
        self.status_code = status_code
        self.org_id = org_id
        super().__init__(self.message)


class MRXClient:
    """
    Reusable MRX Integration Client — token forwarding.

    DRX forwards the caller's Proxzar JWT to MRX.
    MRX verifies it independently via Proxzar JWKS.
    """

    # ══════════════════════════════════════════════════════════
    # Organization Lookup
    # ══════════════════════════════════════════════════════════

    async def _get_org_config(self, org_id: str) -> Dict[str, Any]:
        """
        Read organization's MRX backend URL from DB.
        Returns: backend_url, organization_name
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
        }

    # ══════════════════════════════════════════════════════════
    # Generic Request Method
    # ══════════════════════════════════════════════════════════

    async def request(
        self,
        org_id: str,
        method: str,
        endpoint: str,
        token: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send an authenticated request to an organization's MRX backend.

        Forwards the user's Proxzar JWT as the Authorization header.
        MRX verifies it independently.

        Args:
            org_id: Organization MongoDB _id
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API path (e.g. "/api/v1/integration/drugs")
            token: The user's raw Proxzar JWT (forwarded as Bearer token)
            params: Query parameters
            body: JSON body

        Returns:
            Parsed JSON response from MRX

        Raises:
            MRXClientError: On connection, timeout, or HTTP errors
        """
        config = await self._get_org_config(org_id)
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

        # 401 — Proxzar token invalid/expired. Propagate to caller.
        if response.status_code == 401:
            raise MRXClientError(
                f"MRX rejected the token (401). User must re-authenticate. (org: {config['organization_name']})",
                status_code=401, org_id=org_id
            )

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
        Verify DRX can reach a specific org's MRX backend.
        Only checks connectivity — does not validate tokens.
        """
        try:
            config = await self._get_org_config(org_id)
            return {
                "status": "ok",
                "organization_name": config["organization_name"],
                "backend_url": config["backend_url"]
            }
        except MRXClientError as e:
            return {
                "status": "error",
                "error": e.message,
                "org_id": org_id
            }


# ══════════════════════════════════════════════════════════════
# Singleton instance — import this throughout DRX
# ══════════════════════════════════════════════════════════════
mrx_client = MRXClient()
