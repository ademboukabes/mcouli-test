import httpx
from typing import Any
from app.core.config import settings
from app.core.exceptions import AppException


class McdiService:
    def __init__(self) -> None:
        self.base_url = settings.MCDI_BASE_URL.rstrip("/")
        self.api_key = settings.MCDI_API_KEY
        self.client_id = settings.MCDI_PROJECT_ID

    async def exchange_code(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchanges an OAuth code for a session token and member info."""
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

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    # MCDI standardizes errors
                    error_detail = response.json().get("message", "Failed to exchange MCDI code")
                    raise AppException.unauthorized(f"MCDI Error: {error_detail}")
                return response.json()
            except httpx.RequestError as e:
                raise AppException.internal_error(f"MCDI service unavailable: {e}")

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validates an MCDI session token and fetches live roles."""
        url = f"{self.base_url}/auth/validate"
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "token": token
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise AppException.unauthorized("Invalid or expired MCDI session")
                return response.json()
            except httpx.RequestError as e:
                raise AppException.internal_error(f"MCDI service unavailable: {e}")
