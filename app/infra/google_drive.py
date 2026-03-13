import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.exceptions import AppException
from app.core.config import settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@dataclass
class GoogleTokenResponse:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str
    token_type: str


@dataclass
class GoogleUserInfo:
    id: str
    email: str
    verified_email: bool


class GoogleDriveClient:
    @staticmethod
    def validate_settings() -> None:
        if (
            not settings.GOOGLE_CLIENT_ID
            or not settings.GOOGLE_CLIENT_SECRET
            or not settings.GOOGLE_REDIRECT_URI
        ):
            raise AppException.bad_request(
                "Google Drive OAuth is not configured in environment variables"
            )

    @staticmethod
    def build_consent_url(state: str) -> str:
        GoogleDriveClient.validate_settings()
        query = urllib.parse.urlencode(
            {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "response_type": "code",
                "scope": settings.GOOGLE_OAUTH_SCOPES,
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"{GOOGLE_AUTH_URL}?{query}"

    @staticmethod
    async def exchange_code(code: str) -> GoogleTokenResponse:
        GoogleDriveClient.validate_settings()
        payload = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        data = await GoogleDriveClient._post_form(GOOGLE_TOKEN_URL, payload)
        expires_at = None
        expires_in = data.get("expires_in")
        if isinstance(expires_in, int):
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        return GoogleTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scope=data.get("scope", settings.GOOGLE_OAUTH_SCOPES),
            token_type=data.get("token_type", "Bearer"),
        )

    @staticmethod
    async def get_user_info(access_token: str) -> GoogleUserInfo:
        data = await GoogleDriveClient._get_json(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        return GoogleUserInfo(
            id=data["id"],
            email=data["email"],
            verified_email=bool(data.get("verified_email", False)),
        )

    @staticmethod
    async def _post_form(url: str, payload: dict[str, str]) -> dict[str, object]:
        encoded = urllib.parse.urlencode(payload).encode("utf-8")

        def _request() -> dict[str, object]:
            request = urllib.request.Request(
                url,
                data=encoded,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                raise AppException.bad_request(
                    f"Google token exchange failed: {details or exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                raise AppException.internal_error(
                    "Unable to reach Google OAuth endpoints"
                ) from exc

        return await asyncio.to_thread(_request)

    @staticmethod
    async def _get_json(
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        def _request() -> dict[str, object]:
            request = urllib.request.Request(url, headers=headers or {}, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                raise AppException.bad_request(
                    f"Google user info request failed: {details or exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                raise AppException.internal_error(
                    "Unable to reach Google APIs"
                ) from exc

        return await asyncio.to_thread(_request)
