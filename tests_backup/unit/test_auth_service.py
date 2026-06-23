"""
Unit tests for AuthService.

Tests cover the core mobile auth flow: login, registration, password validation,
blocked user enforcement, session limits, logout, refresh token, and face embedding.
All dependencies (DB queriers, Redis, FaceEmbeddingService) are mocked.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.exceptions import HTTPException

from app.service.users import AuthService
from app.core.securite import hash_password
from app.schema.request.mobile.auth import MobileLoginRequest, MobileRegisterRequest


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_user(
    *,
    user_id: uuid.UUID | None = None,
    email: str = "user@test.com",
    password: str = "Secret123!",
    blocked: bool = False,
    face_embedding: str | None = None,
) -> MagicMock:
    u = MagicMock()
    u.id = user_id or uuid.uuid4()
    u.email = email
    u.hashed_password = hash_password(password)
    u.blocked = blocked
    u.face_embedding = face_embedding
    u.display_name = None
    return u


def _make_session(
    *,
    session_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id or uuid.uuid4()
    s.user_id = user_id or uuid.uuid4()
    s.device_id = uuid.uuid4()
    s.expires_at = expires_at or datetime.now(timezone.utc) + timedelta(days=30)
    s.last_active = datetime.now(timezone.utc)
    return s


def _make_device() -> MagicMock:
    d = MagicMock()
    d.id = uuid.uuid4()
    d.user_id = uuid.uuid4()
    d.is_invalid_token = False
    d.is_active = True
    return d


def _make_login_request(
    *,
    email: str = "user@test.com",
    password: str = "Secret123!",
) -> MobileLoginRequest:
    return MobileLoginRequest(
        email=email,
        password=password,
        device_id=uuid.uuid4(),
        device_name="iPhone 15",
        device_type="ios",
    )


def _make_register_request(
    *,
    email: str = "user@test.com",
    password: str = "Secret123!",
) -> MobileRegisterRequest:
    return MobileRegisterRequest(
        email=email,
        password=password,
        device_id=uuid.uuid4(),
        device_name="iPhone 15",
        device_type="ios",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_querier() -> AsyncMock:
    from db.generated import user as user_queries
    q = MagicMock(spec=user_queries.AsyncQuerier)
    q.get_user_by_email = AsyncMock(return_value=None)
    q.create_user = AsyncMock()
    q.get_user_by_id = AsyncMock()
    q.find_closest_user_by_embedding = AsyncMock(return_value=None)
    q.set_user_embedding = AsyncMock()
    return q


@pytest.fixture
def device_querier() -> AsyncMock:
    from db.generated import devices as device_queries
    q = MagicMock(spec=device_queries.AsyncQuerier)
    q.get_device_by_id = AsyncMock(return_value=None)
    q.create_device = AsyncMock(return_value=_make_device())
    q.activate_device = AsyncMock()
    return q


@pytest.fixture
def session_querier() -> AsyncMock:
    from db.generated import session as session_queries
    q = MagicMock(spec=session_queries.AsyncQuerier)
    q.count_user_sessions = AsyncMock(return_value=0)
    q.upsert_session = AsyncMock(return_value=_make_session())
    q.get_session_by_id = AsyncMock()
    return q


@pytest.fixture
def face_service() -> AsyncMock:
    from app.service.face_embedding import FaceEmbeddingService
    svc = MagicMock(spec=FaceEmbeddingService)
    svc.compute_average_embedding = AsyncMock(return_value=[0.1] * 512)
    return svc


@pytest.fixture
def redis() -> AsyncMock:
    r = MagicMock()
    r.set = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.delete = AsyncMock()
    r.incr = AsyncMock(return_value=1)
    r.expire = AsyncMock()
    return r


@pytest.fixture
def auth_service(
    user_querier: AsyncMock,
    device_querier: AsyncMock,
    session_querier: AsyncMock,
    face_service: AsyncMock,
) -> AuthService:
    return AuthService(
        user_querier=user_querier,
        device_querier=device_querier,
        session_querier=session_querier,
        face_embedding_service=face_service,
    )


# ===========================================================================
# 1. Registration — new user
# ===========================================================================


class TestRegisterNewUser:
    @pytest.mark.asyncio
    async def test_new_user_is_created(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        new_user = _make_user()
        user_querier.get_user_by_email.return_value = None
        user_querier.create_user.return_value = new_user

        req = _make_register_request(email="new@test.com")
        result = await auth_service.mobile_register(redis, req)

        user_querier.create_user.assert_called_once()
        assert result.is_new_user is True

    @pytest.mark.asyncio
    async def test_access_and_refresh_tokens_returned_on_register(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        new_user = _make_user()
        user_querier.get_user_by_email.return_value = None
        user_querier.create_user.return_value = new_user

        result = await auth_service.mobile_register(redis, _make_register_request())

        assert result.access_token
        assert result.refresh_token

    @pytest.mark.asyncio
    async def test_session_cached_in_redis_on_register(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        new_user = _make_user()
        user_querier.get_user_by_email.return_value = None
        user_querier.create_user.return_value = new_user

        await auth_service.mobile_register(redis, _make_register_request())

        # Redis.set must be called at least once (session key)
        redis.set.assert_called()


# ===========================================================================
# 2. Login — existing user
# ===========================================================================


class TestLoginExistingUser:
    @pytest.mark.asyncio
    async def test_valid_credentials_return_tokens(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        existing = _make_user(password="Correctpass1!")
        user_querier.get_user_by_email.return_value = existing

        result = await auth_service.mobile_login(
            redis, _make_login_request(password="Correctpass1!")
        )

        assert result.is_new_user is False
        assert result.access_token

    @pytest.mark.asyncio
    async def test_wrong_password_raises_401(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        existing = _make_user(password="Rightpassword1!")
        user_querier.get_user_by_email.return_value = existing

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.mobile_login(
                redis, _make_login_request(password="Wrongpassword1!")
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_blocked_user_raises_403(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        blocked = _make_user(password="Secret123!", blocked=True)
        user_querier.get_user_by_email.return_value = blocked

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.mobile_login(redis, _make_login_request())
        assert exc_info.value.status_code == 403


# ===========================================================================
# 3. Session limit enforcement
# ===========================================================================


class TestSessionLimit:
    @pytest.mark.asyncio
    async def test_exceeding_session_limit_raises_403(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        user = _make_user()
        user_querier.get_user_by_email.return_value = user
        # Return a count >= SESSION_LIMIT
        session_querier.count_user_sessions.return_value = AuthService.SESSION_LIMIT

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.mobile_login(redis, _make_login_request())
        assert exc_info.value.status_code == 403
        assert "session limit" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_within_session_limit_succeeds(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        user = _make_user()
        user_querier.get_user_by_email.return_value = user
        session_querier.count_user_sessions.return_value = AuthService.SESSION_LIMIT - 1

        result = await auth_service.mobile_login(redis, _make_login_request())
        assert result.access_token


# ===========================================================================
# 4. Logout
# ===========================================================================


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_deletes_session_key_from_redis(
        self,
        auth_service: AuthService,
        redis: AsyncMock,
    ) -> None:
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        await auth_service.logout(redis, user_id, session_id)

        redis.delete.assert_called_once()
        key_used = redis.delete.call_args.args[0]
        assert user_id in key_used

    @pytest.mark.asyncio
    async def test_logout_returns_success_message(
        self,
        auth_service: AuthService,
        redis: AsyncMock,
    ) -> None:
        result = await auth_service.logout(redis, str(uuid.uuid4()), str(uuid.uuid4()))
        assert "message" in result
        assert "logged out" in result["message"].lower()


# ===========================================================================
# 5. Refresh token
# ===========================================================================


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_valid_refresh_returns_new_tokens(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import create_refresh_mobile_token

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(user_id=session.user_id)

        refresh_token = create_refresh_mobile_token(str(session.id))
        result = await auth_service.refresh_token(redis, refresh_token)

        assert result.access_token
        assert result.refresh_token

    @pytest.mark.asyncio
    async def test_expired_session_raises_401(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import create_refresh_mobile_token

        past_session = _make_session(
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
        session_querier.get_session_by_id.return_value = past_session

        refresh_token = create_refresh_mobile_token(str(past_session.id))

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, refresh_token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_blocked_user_on_refresh_raises_403(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import create_refresh_mobile_token

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(
            user_id=session.user_id, blocked=True
        )

        refresh_token = create_refresh_mobile_token(str(session.id))

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, refresh_token)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_raises_401(
        self,
        auth_service: AuthService,
        redis: AsyncMock,
    ) -> None:
        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, "completely.invalid.token")
        assert exc_info.value.status_code == 401


# ===========================================================================
# 6. find_closest_user
# ===========================================================================


class TestFindClosestUser:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_row(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
    ) -> None:
        user_querier.find_closest_user_by_embedding.return_value = None

        result = await auth_service.find_closest_user(embedding_literal="[0.1, 0.2]")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_closest_user_match(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
    ) -> None:
        row = MagicMock()
        row.id = uuid.uuid4()
        row.distance = 0.25
        user_querier.find_closest_user_by_embedding.return_value = row

        result = await auth_service.find_closest_user(embedding_literal="[0.1, 0.2]")

        assert result is not None
        assert result.user_id == row.id
        assert result.distance == 0.25
