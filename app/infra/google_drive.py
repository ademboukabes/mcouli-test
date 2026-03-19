import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import Message

from app.core.exceptions import AppException
from app.core.config import settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files/{file_id}"


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


@dataclass
class GoogleDriveFileMetadata:
    id: str
    name: str
    mime_type: str
    size_bytes: int


@dataclass
class GoogleDriveFileDownload:
    metadata: GoogleDriveFileMetadata
    content: bytes


class GoogleDriveClient:
    @staticmethod
    def _require_str(data: dict[str, object], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise AppException.bad_request(f"Google response missing '{key}'")
        return value

    @staticmethod
    def _optional_str(data: dict[str, object], key: str) -> str | None:
        value = data.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise AppException.bad_request(f"Google response field '{key}' is invalid")
        return value

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
            access_token=GoogleDriveClient._require_str(data, "access_token"),
            refresh_token=GoogleDriveClient._optional_str(data, "refresh_token"),
            expires_at=expires_at,
            scope=GoogleDriveClient._optional_str(data, "scope")
            or settings.GOOGLE_OAUTH_SCOPES,
            token_type=GoogleDriveClient._optional_str(data, "token_type")
            or "Bearer",
        )

    @staticmethod
    async def get_user_info(access_token: str) -> GoogleUserInfo:
        data = await GoogleDriveClient._get_json(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            error_context="Google user info request",
        )
        return GoogleUserInfo(
            id=GoogleDriveClient._require_str(data, "id"),
            email=GoogleDriveClient._require_str(data, "email"),
            verified_email=bool(data.get("verified_email", False)),
        )

    @staticmethod
    async def get_file_metadata(
        *,
        access_token: str,
        file_id: str,
    ) -> GoogleDriveFileMetadata:
        data = await GoogleDriveClient._get_json(
            GOOGLE_DRIVE_FILES_URL.format(file_id=urllib.parse.quote(file_id, safe="")),
            headers={"Authorization": f"Bearer {access_token}"},
            query_params={
                "fields": "id,name,mimeType,size",
                "supportsAllDrives": "true",
            },
            error_context="Google Drive file metadata request",
        )
        size_raw = data.get("size", "0")
        if not isinstance(size_raw, (str, int)):
            raise AppException.bad_request("Google Drive file size is invalid")
        try:
            size_bytes = int(size_raw)
        except (TypeError, ValueError) as exc:
            raise AppException.bad_request("Google Drive file size is invalid") from exc

        return GoogleDriveFileMetadata(
            id=GoogleDriveClient._require_str(data, "id"),
            name=GoogleDriveClient._require_str(data, "name"),
            mime_type=GoogleDriveClient._require_str(data, "mimeType"),
            size_bytes=size_bytes,
        )

    @staticmethod
    async def download_file(
        *,
        access_token: str,
        file_id: str,
    ) -> GoogleDriveFileDownload:
        metadata = await GoogleDriveClient.get_file_metadata(
            access_token=access_token,
            file_id=file_id,
        )
        content, _, _ = await GoogleDriveClient._get_bytes(
            GOOGLE_DRIVE_FILES_URL.format(file_id=urllib.parse.quote(file_id, safe="")),
            headers={"Authorization": f"Bearer {access_token}"},
            query_params={
                "alt": "media",
                "supportsAllDrives": "true",
            },
        )
        return GoogleDriveFileDownload(metadata=metadata, content=content)

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
        query_params: dict[str, str] | None = None,
        error_context: str = "Google API request",
    ) -> dict[str, object]:
        def _request() -> dict[str, object]:
            final_url = url
            if query_params:
                final_url = f"{url}?{urllib.parse.urlencode(query_params)}"
            request = urllib.request.Request(final_url, headers=headers or {}, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                raise AppException.bad_request(
                    f"{error_context} failed: {details or exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                raise AppException.internal_error(
                    "Unable to reach Google APIs"
                ) from exc

        return await asyncio.to_thread(_request)

    @staticmethod
    async def _get_bytes(
        url: str,
        headers: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> tuple[bytes, str, str]:
        def _request() -> tuple[bytes, str, str]:
            final_url = url
            if query_params:
                final_url = f"{url}?{urllib.parse.urlencode(query_params)}"
            request = urllib.request.Request(final_url, headers=headers or {}, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read()
                    response_headers: Message = response.headers
                    content_type = response_headers.get_content_type()
                    file_name = response_headers.get_filename() or ""
                    return body, content_type, file_name
            except urllib.error.HTTPError as exc:
                details = exc.read().decode("utf-8", errors="ignore")
                raise AppException.bad_request(
                    f"Google file download failed: {details or exc.reason}"
                ) from exc
            except urllib.error.URLError as exc:
                raise AppException.internal_error("Unable to download file from Google Drive") from exc

        return await asyncio.to_thread(_request)
