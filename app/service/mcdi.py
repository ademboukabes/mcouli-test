import hashlib
import json
import logging
import urllib.parse
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppException
from app.infra.redis import RedisClient

logger = logging.getLogger(__name__)


class McdiService:
    def __init__(self) -> None:
        self.base_url = settings.MCDI_BASE_URL.rstrip("/")
        self.api_key = settings.MCDI_API_KEY
        self.client_id = settings.MCDI_PROJECT_ID
        self.server_id = settings.MCDI_SERVER_ID
        self._timeout = httpx.Timeout(10.0, connect=5.0)

    def get_sso_authorize_url(self, redirect_uri: str, state: str) -> str:
        """Constructs the MCDI SSO authorization URL matching MCDI's AuthorizeQueryDto."""
        params = urllib.parse.urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "server_id": self.server_id,
            "state": state,
        })
        # MCDI_BASE_URL ends with /api (e.g. https://mcdi.microclub.info/api)
        # The authorize route is /api/auth/sso/authorize
        return f"{self.base_url}/auth/sso/authorize?{params}"

    @staticmethod
    def _parse_error_detail(response: httpx.Response, default: str) -> str:
        try:
            body = response.json()
            msg = body.get("message")
            if isinstance(msg, list):
                return ", ".join(str(m) for m in msg)
            if isinstance(msg, str) and msg:
                return msg
            err = body.get("error")
            if isinstance(err, str) and err:
                return err
        except Exception:
            pass
        return default

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchanges an OAuth callback code for a long-lived MCDI session token."""
        url = f"{self.base_url}/auth/token"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "clientId": self.client_id,
            "code": code,
            "redirectUri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    detail = self._parse_error_detail(response, "Failed to exchange MCDI code")
                    logger.warning("mcdi_exchange_failed status=%d detail=%s", response.status_code, detail)
                    raise AppException.unauthorized(f"MCDI Error: {detail}")
                return response.json()
            except httpx.RequestError as e:
                logger.error("mcdi_network_error url=%s err=%s", url, e)
                raise AppException.internal_error(f"MCDI service unavailable: {e}")

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validates an MCDI session token and fetches live roles directly from MCDI."""
        url = f"{self.base_url}/auth/validate"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"token": token}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    detail = self._parse_error_detail(response, "Invalid or expired MCDI session")
                    logger.warning("mcdi_validation_failed status=%d detail=%s", response.status_code, detail)
                    raise AppException.unauthorized(f"MCDI validation failed: {detail}")
                return response.json()
            except httpx.RequestError as e:
                logger.error("mcdi_network_error url=%s err=%s", url, e)
                raise AppException.internal_error(f"MCDI service unavailable: {e}")

    async def validate_token_cached(
        self,
        redis: RedisClient,
        token: str,
        ttl_seconds: int = 60,
    ) -> dict[str, Any]:
        """
        Validates token against Redis cache to prevent latency and avoid hitting MCDI rate limits
        (MCDI limits /auth/validate to 60 req/min). Falls back to remote validation on cache miss.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        cache_key = f"mcdi:session:{token_hash}"

        cached = await redis.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        # Cache miss: validate against MCDI
        data = await self.validate_token(token)
        try:
            await redis.set(cache_key, json.dumps(data), expire=ttl_seconds)
        except Exception as e:
            logger.warning("mcdi_cache_write_failed err=%s", e)

        return data

    async def logout(self, token: str, redis: RedisClient | None = None) -> bool:
        """Kills the project-scoped session on MCDI and purges local Redis validation cache."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if redis:
            try:
                await redis.delete(f"mcdi:session:{token_hash}")
            except Exception as e:
                logger.warning("mcdi_cache_delete_failed err=%s", e)

        url = f"{self.base_url}/auth/logout"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {"token": token}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                return response.status_code == 200
            except Exception as e:
                logger.warning("mcdi_logout_failed err=%s", e)
                return False
