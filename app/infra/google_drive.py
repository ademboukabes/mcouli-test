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
from app.core.constant import (
    GOOGLE_AUTH_URL,
    GOOGLE_DRIVE_FILES_URL,
    GOOGLE_TOKEN_URL,
    GOOGLE_USERINFO_URL,
)
GOOGLE_DRIVE_LIST_FILES_URL = "https://www.googleapis.com/drive/v3/files"


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
    _drive_folder_mime_type = "application/vnd.google-apps.folder"

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
    async def refresh_access_token(refresh_token: str) -> GoogleTokenResponse:
        GoogleDriveClient.validate_settings()
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
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
    async def list_folder_files(
        *,
        access_token: str,
        folder_id: str,
    ) -> list[GoogleDriveFileMetadata]:
        files: list[GoogleDriveFileMetadata] = []
        next_page_token: str | None = None

        while True:
            query_params = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "pageSize": "100",
            }
            if next_page_token is not None:
                query_params["pageToken"] = next_page_token

            data = await GoogleDriveClient._get_json(
                GOOGLE_DRIVE_LIST_FILES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                query_params=query_params,
                error_context="Google Drive folder listing request",
            )

            raw_files = data.get("files", [])
            if not isinstance(raw_files, list):
                raise AppException.bad_request("Google Drive folder listing response is invalid")

            for raw_file in raw_files:
                if not isinstance(raw_file, dict):
                    raise AppException.bad_request("Google Drive folder entry is invalid")
                metadata = GoogleDriveClient._file_metadata_from_dict(raw_file)
                if metadata.mime_type == GoogleDriveClient._drive_folder_mime_type:
                    continue
                files.append(metadata)

            next_page_token_raw = data.get("nextPageToken")
            if next_page_token_raw is None:
                break
            if not isinstance(next_page_token_raw, str) or not next_page_token_raw:
                raise AppException.bad_request("Google Drive next page token is invalid")
            next_page_token = next_page_token_raw

        return files

    @staticmethod
    async def list_folder_contents(
        *,
        access_token: str,
        folder_id: str | None = None,
    ) -> list[GoogleDriveFileMetadata]:
        """Like list_folder_files but includes folders. folder_id=None means root."""
        parent = folder_id or "root"
        items: list[GoogleDriveFileMetadata] = []
        next_page_token: str | None = None

        while True:
            query_params = {
                "q": f"'{parent}' in parents and trashed = false",
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "pageSize": "100",
            }
            if next_page_token is not None:
                query_params["pageToken"] = next_page_token

            data = await GoogleDriveClient._get_json(
                GOOGLE_DRIVE_LIST_FILES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                query_params=query_params,
                error_context="Google Drive folder browse request",
            )

            raw_files = data.get("files", [])
            if not isinstance(raw_files, list):
                raise AppException.bad_request("Google Drive folder listing response is invalid")

            for raw_file in raw_files:
                if not isinstance(raw_file, dict):
                    continue
                items.append(GoogleDriveClient._file_metadata_from_dict(raw_file))

            next_page_token_raw = data.get("nextPageToken")
            if not isinstance(next_page_token_raw, str) or not next_page_token_raw:
                break
            next_page_token = next_page_token_raw

        return items

    @staticmethod
    async def search_files(
        *,
        access_token: str,
        query: str,
        file_type: str | None = None,
    ) -> list[GoogleDriveFileMetadata]:
        """Search Drive by name. file_type can be 'folder' or 'image'."""
        q_parts = [f"name contains '{query}'", "trashed = false"]
        if file_type == "folder":
            q_parts.append(f"mimeType = '{GoogleDriveClient._drive_folder_mime_type}'")
        elif file_type == "image":
            q_parts.append("mimeType contains 'image/'")

        items: list[GoogleDriveFileMetadata] = []
        next_page_token: str | None = None

        while True:
            query_params = {
                "q": " and ".join(q_parts),
                "fields": "nextPageToken,files(id,name,mimeType,size)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
                "pageSize": "100",
            }
            if next_page_token is not None:
                query_params["pageToken"] = next_page_token

            data = await GoogleDriveClient._get_json(
                GOOGLE_DRIVE_LIST_FILES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                query_params=query_params,
                error_context="Google Drive search request",
            )

            raw_files = data.get("files", [])
            if not isinstance(raw_files, list):
                break

            for raw_file in raw_files:
                if not isinstance(raw_file, dict):
                    continue
                items.append(GoogleDriveClient._file_metadata_from_dict(raw_file))

            next_page_token_raw = data.get("nextPageToken")
            if not isinstance(next_page_token_raw, str) or not next_page_token_raw:
                break
            next_page_token = next_page_token_raw

        return items

    @staticmethod
    def _file_metadata_from_dict(data: dict[str, object]) -> GoogleDriveFileMetadata:
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
