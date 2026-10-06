import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.schema.request.mobile.auth import McdiExchangeRequest
from app.service.mcdi import McdiService
from app.service.users import AuthService


@pytest.fixture
def mcdi_service() -> McdiService:
    return McdiService()


def test_get_sso_authorize_url(mcdi_service: McdiService) -> None:
    redirect_uri = "https://app.example.com/callback"
    state = "random-state-123"
    url = mcdi_service.get_sso_authorize_url(redirect_uri, state)

    assert "/auth/sso/authorize?" in url
    assert f"client_id={settings.MCDI_PROJECT_ID}" in url
    assert f"server_id={settings.MCDI_SERVER_ID}" in url
    assert "state=random-state-123" in url
    assert "redirect_uri=https%3A%2F%2Fapp.example.com%2Fcallback" in url


@pytest.mark.asyncio
async def test_exchange_code_success(mcdi_service: McdiService) -> None:
    expected_response = {
        "token": "sess_123456",
        "member": {
            "id": "discord_999",
            "username": "alice",
            "email": "alice@microclub.info",
            "isClubMember": True,
        },
        "roles": [{"roleId": "r1", "roleName": "Bureau"}],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = expected_response

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        res = await mcdi_service.exchange_code("code_abc", "https://redirect.uri")

        assert res["token"] == "sess_123456"
        assert res["member"]["id"] == "discord_999"
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["code"] == "code_abc"
        assert kwargs["json"]["clientId"] == settings.MCDI_PROJECT_ID


@pytest.mark.asyncio
async def test_exchange_code_failure(mcdi_service: McdiService) -> None:
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"message": "Invalid callback code"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(HTTPException) as exc_info:
            await mcdi_service.exchange_code("bad_code", "https://redirect.uri")
        assert "Invalid callback code" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_validate_token_cached_hit(mcdi_service: McdiService) -> None:
    redis = AsyncMock()
    cached_payload = {
        "member": {"id": "123", "email": "alice@club.net"},
        "roles": [],
    }
    redis.get.return_value = json.dumps(cached_payload)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        data = await mcdi_service.validate_token_cached(redis, "token_xyz", ttl_seconds=60)
        assert data == cached_payload
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_validate_token_cached_miss_populates_cache(mcdi_service: McdiService) -> None:
    redis = AsyncMock()
    redis.get.return_value = None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    remote_payload = {
        "member": {"id": "123", "email": "alice@club.net"},
        "roles": [],
    }
    mock_resp.json.return_value = remote_payload

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        data = await mcdi_service.validate_token_cached(redis, "token_xyz", ttl_seconds=60)

        assert data == remote_payload
        mock_post.assert_called_once()
        redis.set.assert_called_once()
        call_args = redis.set.call_args
        assert call_args[1]["expire"] == 60


@pytest.mark.asyncio
async def test_logout_invalidates_cache_and_calls_mcdi(mcdi_service: McdiService) -> None:
    redis = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        ok = await mcdi_service.logout("token_to_kill", redis=redis)

        assert ok is True
        redis.delete.assert_called_once()
        mock_post.assert_called_once()
        assert "/auth/logout" in mock_post.call_args[0][0]


@pytest.mark.asyncio
async def test_users_service_mcdi_exchange_creates_new_user() -> None:
    user_querier = AsyncMock()
    device_querier = AsyncMock()
    session_querier = AsyncMock()
    refresh_token_querier = AsyncMock()
    face_service = MagicMock()
    mock_mcdi = AsyncMock()
    redis = AsyncMock()
    redis.incr.return_value = 1

    auth_service = AuthService(
        user_querier=user_querier,
        device_querier=device_querier,
        session_querier=session_querier,
        refresh_token_querier=refresh_token_querier,
        face_embedding_service=face_service,
        mcdi_service=mock_mcdi,
    )

    mock_mcdi.exchange_code.return_value = {
        "token": "mcdi_sess_tok",
        "member": {
            "id": "discord_12345",
            "email": "bob@microclub.info",
            "username": "bob",
        },
    }

    user_querier.get_user_by_discord_id.return_value = None
    user_querier.get_user_by_email.return_value = None

    new_user_mock = MagicMock()
    new_user_mock.id = uuid.uuid4()
    new_user_mock.email = "bob@microclub.info"
    new_user_mock.blocked = False
    user_querier.create_user.return_value = new_user_mock
    user_querier.get_user_by_id_for_update.return_value = new_user_mock

    device_mock = MagicMock()
    device_mock.id = uuid.uuid4()
    device_querier.get_device_by_physical_id.return_value = None
    device_querier.create_device.return_value = device_mock

    session_mock = MagicMock()
    session_mock.id = uuid.uuid4()
    session_mock.user_id = new_user_mock.id
    session_mock.idle_expires_at = MagicMock()
    session_mock.absolute_expires_at = MagicMock()
    session_mock.last_active = MagicMock()
    session_querier.upsert_session.return_value = session_mock

    async def _empty_async_iter(*args, **kwargs):
        if False:
            yield

    session_querier.evict_overflow_sessions = MagicMock(side_effect=_empty_async_iter)

    req = McdiExchangeRequest(
        code="code_from_discord",
        device_name="iPhone 15",
        device_type="ios",
        physical_device_id=uuid.uuid4(),
    )

    res = await auth_service.mcdi_exchange(redis, req)

    assert res.is_new_user is True
    assert res.user_id == new_user_mock.id
    user_querier.create_user.assert_called_once_with(
        email="bob@microclub.info",
        hashed_password=None,
        discord_id="discord_12345",
    )


@pytest.mark.asyncio
async def test_users_service_mcdi_exchange_links_existing_user() -> None:
    user_querier = AsyncMock()
    device_querier = AsyncMock()
    session_querier = AsyncMock()
    refresh_token_querier = AsyncMock()
    face_service = MagicMock()
    mock_mcdi = AsyncMock()
    redis = AsyncMock()
    redis.incr.return_value = 1

    auth_service = AuthService(
        user_querier=user_querier,
        device_querier=device_querier,
        session_querier=session_querier,
        refresh_token_querier=refresh_token_querier,
        face_embedding_service=face_service,
        mcdi_service=mock_mcdi,
    )

    mock_mcdi.exchange_code.return_value = {
        "token": "mcdi_sess_tok_2",
        "member": {
            "id": "discord_existing_123",
            "email": "existing@microclub.info",
            "username": "existing_user",
        },
    }

    existing_user = MagicMock()
    existing_user.id = uuid.uuid4()
    existing_user.email = "existing@microclub.info"
    existing_user.blocked = False

    user_querier.get_user_by_discord_id.return_value = None
    user_querier.get_user_by_email.return_value = existing_user
    user_querier.update_user_discord_id.return_value = existing_user
    user_querier.get_user_by_id_for_update.return_value = existing_user

    device_mock = MagicMock()
    device_mock.id = uuid.uuid4()
    device_querier.get_device_by_physical_id.return_value = None
    device_querier.create_device.return_value = device_mock

    session_mock = MagicMock()
    session_mock.id = uuid.uuid4()
    session_mock.user_id = existing_user.id
    session_mock.idle_expires_at = MagicMock()
    session_mock.absolute_expires_at = MagicMock()
    session_mock.last_active = MagicMock()
    session_querier.upsert_session.return_value = session_mock

    async def _empty_async_iter(*args, **kwargs):
        if False:
            yield

    session_querier.evict_overflow_sessions = MagicMock(side_effect=_empty_async_iter)

    req = McdiExchangeRequest(
        code="code_existing",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    res = await auth_service.mcdi_exchange(redis, req)

    assert res.is_new_user is False
    assert res.user_id == existing_user.id
    user_querier.update_user_discord_id.assert_called_once_with(
        discord_id="discord_existing_123",
        id=existing_user.id,
    )
    user_querier.create_user.assert_not_called()


@pytest.mark.asyncio
async def test_cookie_auth_get_current_staff_user_success() -> None:
    from app.deps.cookie_auth import get_current_staff_user

    container = MagicMock()
    container.redis = AsyncMock()
    container.mcdi_service = AsyncMock()
    container.staff_user_querier = AsyncMock()

    container.mcdi_service.validate_token_cached.return_value = {
        "member": {"email": "admin@microclub.info", "id": "111"},
        "roles": [{"roleName": "Admin"}],
    }

    mock_staff = MagicMock()
    mock_staff.email = "admin@microclub.info"
    container.staff_user_querier.get_staff_user_by_email.return_value = mock_staff

    staff = await get_current_staff_user(container=container, token="valid_staff_tok")
    assert staff == mock_staff


@pytest.mark.asyncio
async def test_cookie_auth_get_current_staff_user_unauthorized_if_not_staff() -> None:
    from app.deps.cookie_auth import get_current_staff_user

    container = MagicMock()
    container.redis = AsyncMock()
    container.mcdi_service = AsyncMock()
    container.staff_user_querier = AsyncMock()

    container.mcdi_service.validate_token_cached.return_value = {
        "member": {"email": "stranger@discord.com", "id": "999"},
        "roles": [],
    }

    container.staff_user_querier.get_staff_user_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_current_staff_user(container=container, token="valid_mcdi_tok")
    assert exc_info.value.status_code == 401
    assert "not authorized" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_token_auth_validate_mcdi_session_revoked() -> None:
    from app.deps.token_auth import _validate_mcdi_session

    container = MagicMock()
    redis = AsyncMock()
    container.mcdi_service = AsyncMock()
    container.mcdi_service.validate_token_cached.side_effect = Exception("revoked")
    
    with pytest.raises(HTTPException) as exc_info:
        await _validate_mcdi_session(container, redis, "revoked_tok")
    assert exc_info.value.status_code == 401
    assert "MCDI session invalid" in exc_info.value.detail

