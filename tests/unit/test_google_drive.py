import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.infra.google_drive import (
    GoogleDriveClient,
)


@pytest.fixture(autouse=True)
def mock_google_settings(monkeypatch):
    """Ensure tests run with deterministic and safe config without real env vars."""
    monkeypatch.setattr("app.core.config.settings.GOOGLE_CLIENT_ID", "mock_client_id")
    monkeypatch.setattr(
        "app.core.config.settings.GOOGLE_CLIENT_SECRET", "mock_client_secret"
    )
    monkeypatch.setattr(
        "app.core.config.settings.GOOGLE_REDIRECT_URI", "mock_redirect_uri"
    )
    monkeypatch.setattr("app.core.config.settings.GOOGLE_OAUTH_SCOPES", "mock_scopes")


def create_mock_response(
    body_dict: dict = None, body_bytes: bytes = None, headers: dict = None
):
    """Helper to mock urllib.request.urlopen returned context manager."""
    mock_resp = MagicMock()
    if body_dict is not None:
        mock_resp.read.return_value = json.dumps(body_dict).encode("utf-8")
    elif body_bytes is not None:
        mock_resp.read.return_value = body_bytes

    mock_headers = MagicMock()
    if headers:
        mock_headers.get_content_type.return_value = headers.get("Content-Type", "")
        mock_headers.get_filename.return_value = headers.get("Content-Disposition", "")
    mock_resp.headers = mock_headers

    mock_resp.__enter__.return_value = mock_resp
    return mock_resp


def create_http_error(code: int, reason: str, json_body: dict):
    """Helper to simulate HTTPError like invalid_grant or 403."""
    body_bytes = json.dumps(json_body).encode("utf-8")
    fp = io.BytesIO(body_bytes)
    return urllib.error.HTTPError(url="", code=code, msg=reason, hdrs={}, fp=fp)


def test_build_consent_url():
    url = GoogleDriveClient.build_consent_url("mock_state")
    assert "client_id=mock_client_id" in url
    assert "redirect_uri=mock_redirect_uri" in url
    assert "state=mock_state" in url
    assert "prompt=consent" in url


@pytest.mark.asyncio
async def test_exchange_code_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = create_mock_response(
            {
                "access_token": "valid_access_token",
                "refresh_token": "valid_refresh_token",
                "expires_in": 3600,
                "scope": "custom_scope",
                "token_type": "Bearer",
            }
        )
        token = await GoogleDriveClient.exchange_code("mock_code")
        assert token.access_token == "valid_access_token"
        assert token.refresh_token == "valid_refresh_token"
        assert token.expires_at is not None
        assert token.scope == "custom_scope"
        assert token.token_type == "Bearer"


@pytest.mark.asyncio
async def test_exchange_code_http_error():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = create_http_error(
            400, "Bad Request", {"error": "invalid_grant"}
        )
        with pytest.raises(HTTPException) as exc:
            await GoogleDriveClient.exchange_code("mock_code")
        assert "invalid_grant" in exc.value.detail


@pytest.mark.asyncio
async def test_get_user_info_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = create_mock_response(
            {"id": "12345", "email": "test@multai.com", "verified_email": True}
        )
        info = await GoogleDriveClient.get_user_info("mock_access_token")
        assert info.id == "12345"
        assert info.email == "test@multai.com"
        assert info.verified_email is True


@pytest.mark.asyncio
async def test_get_file_metadata_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = create_mock_response(
            {
                "id": "file_123",
                "name": "photo.jpg",
                "mimeType": "image/jpeg",
                "size": "1048576",
            }
        )
        metadata = await GoogleDriveClient.get_file_metadata(
            access_token="tok", file_id="file_123"
        )
        assert metadata.id == "file_123"
        assert metadata.name == "photo.jpg"
        assert metadata.mime_type == "image/jpeg"
        assert metadata.size_bytes == 1048576


@pytest.mark.asyncio
async def test_get_file_metadata_invalid_size():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value = create_mock_response(
            {
                "id": "file_123",
                "name": "photo.jpg",
                "mimeType": "image/jpeg",
                "size": "invalid_size",
            }
        )
        with pytest.raises(HTTPException) as exc:
            await GoogleDriveClient.get_file_metadata(
                access_token="tok", file_id="file_123"
            )
        assert "file size is invalid" in exc.value.detail


@pytest.mark.asyncio
async def test_download_file_success():
    with patch("urllib.request.urlopen") as mock_urlopen:
        # First call gets metadata
        resp1 = create_mock_response(
            {
                "id": "file_123",
                "name": "photo.jpg",
                "mimeType": "image/jpeg",
                "size": "500",
            }
        )
        # Second call gets actual bytes
        resp2 = create_mock_response(
            body_bytes=b"fake_image_content",
            headers={"Content-Type": "image/jpeg", "Content-Disposition": "photo.jpg"},
        )
        mock_urlopen.side_effect = [resp1, resp2]

        download = await GoogleDriveClient.download_file(
            access_token="tok", file_id="file_123"
        )
        assert download.metadata.id == "file_123"
        assert download.content == b"fake_image_content"


@pytest.mark.asyncio
async def test_list_folder_files_pagination_and_filtering():
    with patch("urllib.request.urlopen") as mock_urlopen:
        # First page returns a file and a folder (folder should be filtered out)
        resp1 = create_mock_response(
            {
                "nextPageToken": "page2_token",
                "files": [
                    {
                        "id": "file1",
                        "name": "1.jpg",
                        "mimeType": "image/jpeg",
                        "size": "100",
                    },
                    {
                        "id": "folder1",
                        "name": "subfolder",
                        "mimeType": "application/vnd.google-apps.folder",
                        "size": "0",
                    },
                ],
            }
        )
        # Second page returns just one file and no page token
        resp2 = create_mock_response(
            {
                "files": [
                    {
                        "id": "file2",
                        "name": "2.jpg",
                        "mimeType": "image/jpeg",
                        "size": "200",
                    }
                ]
            }
        )
        mock_urlopen.side_effect = [resp1, resp2]

        files = await GoogleDriveClient.list_folder_files(
            access_token="tok", folder_id="folder_123"
        )
        assert len(files) == 2
        assert files[0].id == "file1"
        assert files[1].id == "file2"
        # Ensure it called urlopen twice to handle the nextPageToken
        assert mock_urlopen.call_count == 2


@pytest.mark.asyncio
async def test_search_files_filters():
    with patch("urllib.request.urlopen") as mock_urlopen:
        resp = create_mock_response(
            {
                "files": [
                    {
                        "id": "file1",
                        "name": "match.jpg",
                        "mimeType": "image/jpeg",
                        "size": "100",
                    }
                ]
            }
        )
        mock_urlopen.return_value = resp

        files = await GoogleDriveClient.search_files(
            access_token="tok", query="match", file_type="image"
        )
        assert len(files) == 1
        assert files[0].id == "file1"

        # Check if query constructed properly
        request_obj = mock_urlopen.call_args[0][0]
        assert (
            "mimeType+contains+%27image%2F%27" in request_obj.full_url
            or "mimeType contains 'image/'"
            in urllib.parse.unquote(request_obj.full_url)
        )
