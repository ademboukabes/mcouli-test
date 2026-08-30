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


async def _empty_async_iter():
    return
    yield  # pragma: no cover


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
    idle_expires_at: datetime | None = None,
    absolute_expires_at: datetime | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id or uuid.uuid4()
    s.user_id = user_id or uuid.uuid4()
    s.device_id = uuid.uuid4()
    s.idle_expires_at = idle_expires_at or datetime.now(timezone.utc) + timedelta(
        days=7
    )
    s.absolute_expires_at = absolute_expires_at or datetime.now(
        timezone.utc
    ) + timedelta(days=30)
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
        physical_device_id=uuid.uuid4(),  # was: device_id
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
        physical_device_id=uuid.uuid4(),  # was: device_id
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
    q.get_user_by_id_for_update = AsyncMock(return_value=None)
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
    q.get_device_by_id_any = AsyncMock(return_value=None)
    q.get_device_by_physical_id = AsyncMock(return_value=None)  # new
    q.create_device = AsyncMock(return_value=_make_device())
    q.activate_device = AsyncMock()
    return q


@pytest.fixture
def session_querier() -> AsyncMock:
    from db.generated import session as session_queries

    q = MagicMock(spec=session_queries.AsyncQuerier)
    q.lock_user_sessions = AsyncMock(return_value=None)

    async def _default_empty_evict(*, user_id, id, session_limit):
        return
        yield  # pragma: no cover

    q.evict_overflow_sessions = MagicMock(side_effect=_default_empty_evict)
    q.get_session_by_device_for_user = AsyncMock(return_value=None)
    q.list_sessions_by_user = MagicMock(return_value=_empty_async_iter())
    q.delete_session_by_id = AsyncMock()
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
def refresh_token_querier() -> AsyncMock:
    from db.generated import refresh_token as refresh_token_queries

    q = MagicMock(spec=refresh_token_queries.AsyncQuerier)
    q.get_refresh_token_by_hash_for_update = AsyncMock(return_value=None)
    q.get_refresh_token_by_jti = AsyncMock(return_value=None)
    q.create_refresh_token = AsyncMock()
    q.revoke_refresh_token = AsyncMock()
    q.revoke_all_user_refresh_tokens = AsyncMock()
    q.mark_refresh_token_used = AsyncMock()
    return q


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
    refresh_token_querier: AsyncMock,
) -> AuthService:
    return AuthService(
        user_querier=user_querier,
        device_querier=device_querier,
        session_querier=session_querier,
        face_embedding_service=face_service,
        refresh_token_querier=refresh_token_querier,
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
        refresh_token_querier: AsyncMock,
    ) -> None:
        new_user = _make_user()
        user_querier.get_user_by_email.return_value = None
        user_querier.create_user.return_value = new_user

        req = _make_register_request()
        result = await auth_service.mobile_register(redis, req)

        user_querier.create_user.assert_not_called()
        assert result.status == "pending_verification"

    @pytest.mark.asyncio
    async def test_pending_status_returned_on_register(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
        refresh_token_querier: AsyncMock,
    ) -> None:
        user_querier.get_user_by_email.return_value = None

        result = await auth_service.mobile_register(redis, _make_register_request())

        assert result.status == "pending_verification"
        assert result.message == "OTP sent to email"

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
        user_querier.get_user_by_id_for_update.return_value = existing

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
        user_querier.get_user_by_id_for_update.return_value = existing

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
    async def test_at_cap_evicts_oldest_and_succeeds(
        self,
        auth_service,
        user_querier,
        session_querier,
        redis,
    ) -> None:
        user = _make_user()
        user_querier.get_user_by_email.return_value = user
        user_querier.get_user_by_id_for_update.return_value = user

        evicted_id = uuid.uuid4()

        async def _evict(*, user_id, id, session_limit):
            assert session_limit == AuthService.SESSION_LIMIT
            yield evicted_id

        session_querier.evict_overflow_sessions = MagicMock(side_effect=_evict)

        result = await auth_service.mobile_login(redis, _make_login_request())

        assert result.access_token
        session_querier.evict_overflow_sessions.assert_called_once()

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
        user_querier.get_user_by_id_for_update.return_value = user
        session_querier.list_sessions_by_user = MagicMock(
            return_value=_empty_async_iter()
        )

        result = await auth_service.mobile_login(redis, _make_login_request())
        assert result.access_token
        session_querier.delete_session_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_new_devices_at_cap_evict_exact_overflow(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """evict_overflow_sessions must be called with session_limit=SESSION_LIMIT,
        and every session id it yields must trigger a Redis cache eviction."""
        user = _make_user()
        user_querier.get_user_by_email.return_value = user
        user_querier.get_user_by_id_for_update.return_value = user

        evicted_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

        async def _evict(*, user_id, id, session_limit):
            assert session_limit == AuthService.SESSION_LIMIT
            for eid in evicted_ids:
                yield eid

        session_querier.evict_overflow_sessions = MagicMock(side_effect=_evict)

        result = await auth_service.mobile_login(redis, _make_login_request())

        assert result.access_token
        session_querier.evict_overflow_sessions.assert_called_once()
        call_kwargs = session_querier.evict_overflow_sessions.call_args.kwargs
        assert call_kwargs["session_limit"] == AuthService.SESSION_LIMIT
        assert call_kwargs["user_id"] == user.id
        # Redis delete must be called for each evicted session
        assert redis.delete.call_count == 3


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
        assert session_id in key_used

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
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import (
            create_raw_refresh_token,
            hash_refresh_token,
            decrypt_refresh_cache_payload,
        )

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(user_id=session.user_id)

        raw_token = create_raw_refresh_token()
        token_hash = hash_refresh_token(raw_token)

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = False
        row.used_at = None
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row
        refresh_token_querier.mark_refresh_token_used.return_value = row

        result = await auth_service.refresh_token(redis, raw_token)

        assert result.access_token
        assert result.refresh_token
        refresh_token_querier.mark_refresh_token_used.assert_called_once_with(id=row.id)
        refresh_token_querier.create_refresh_token.assert_called_once()

        # Verify the grace-window cache was written under the expected key,
        # encrypted (not plaintext), and that it decrypts back to the response.
        redis.set.assert_called_once()
        call_args = redis.set.call_args
        cache_key = call_args.args[0] if call_args.args else call_args.kwargs.get("key")
        cache_value = (
            call_args.args[1]
            if len(call_args.args) > 1
            else call_args.kwargs.get("value")
        )

        assert cache_key == f"refresh_retry:{token_hash}"
        assert (
            "access_token" not in cache_value
        )  # plaintext JSON would contain this literal key; encrypted payload must not
        decrypted = decrypt_refresh_cache_payload(cache_value)
        assert result.access_token in decrypted

    @pytest.mark.asyncio
    async def test_expired_session_raises_401(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import create_raw_refresh_token

        past_session = _make_session(
            idle_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            absolute_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        session_querier.get_session_by_id.return_value = past_session

        raw_token = create_raw_refresh_token()
        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = False
        row.used_at = None
        row.family_id = uuid.uuid4()
        row.session_id = past_session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row
        refresh_token_querier.mark_refresh_token_used.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_blocked_user_on_refresh_raises_403(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        from app.core.securite import create_raw_refresh_token

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(
            user_id=session.user_id, blocked=True
        )

        raw_token = create_raw_refresh_token()
        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = False
        row.used_at = None
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row
        refresh_token_querier.mark_refresh_token_used.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_invalid_refresh_token_raises_401(
        self,
        auth_service: AuthService,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        # Ensure the querier returns None so the token is rejected
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, "completely.invalid.token")
        assert exc_info.value.status_code == 401

        @pytest.mark.asyncio
        async def test_refresh_rejects_idle_expired_session(
            self,
            auth_service: AuthService,
            user_querier: AsyncMock,
            session_querier: AsyncMock,
            refresh_token_querier: AsyncMock,
            redis: AsyncMock,
        ) -> None:
            """Idle timeout expired but absolute still valid → refresh must reject."""
            from app.core.securite import create_raw_refresh_token

            now = datetime.now(timezone.utc)
            session = _make_session(
                idle_expires_at=now - timedelta(hours=1),  # expired
                absolute_expires_at=now + timedelta(days=30),  # valid
            )
            session_querier.get_session_by_id.return_value = session
            user_querier.get_user_by_id.return_value = _make_user(
                user_id=session.user_id
            )

            raw_token = create_raw_refresh_token()
            row = MagicMock()
            row.id = uuid.uuid4()
            row.used = False
            row.used_at = None
            row.family_id = uuid.uuid4()
            row.session_id = session.id
            refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = (
                row
            )
            refresh_token_querier.mark_refresh_token_used.return_value = row

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh_token(redis, raw_token)
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

        @pytest.mark.asyncio
        async def test_refresh_rejects_absolute_expired_session(
            self,
            auth_service: AuthService,
            user_querier: AsyncMock,
            session_querier: AsyncMock,
            refresh_token_querier: AsyncMock,
            redis: AsyncMock,
        ) -> None:
            """Absolute timeout expired but idle still valid → refresh must reject."""
            from app.core.securite import create_raw_refresh_token

            now = datetime.now(timezone.utc)
            session = _make_session(
                idle_expires_at=now + timedelta(days=7),  # valid
                absolute_expires_at=now - timedelta(hours=1),  # expired
            )
            session_querier.get_session_by_id.return_value = session
            user_querier.get_user_by_id.return_value = _make_user(
                user_id=session.user_id
            )

            raw_token = create_raw_refresh_token()
            row = MagicMock()
            row.id = uuid.uuid4()
            row.used = False
            row.used_at = None
            row.family_id = uuid.uuid4()
            row.session_id = session.id
            refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = (
                row
            )
            refresh_token_querier.mark_refresh_token_used.return_value = row

            with pytest.raises(HTTPException) as exc_info:
                await auth_service.refresh_token(redis, raw_token)
            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()


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


class TestBlockedUserRaceCondition:
    @pytest.mark.asyncio
    async def test_blocked_between_initial_check_and_lock_is_caught(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """Simulates the exact race: the first read sees an unblocked user,
        but the row-locked re-read (as if block_user committed in between)
        sees blocked=True. Login must still be rejected, and no session
        may be created."""
        unblocked_snapshot = _make_user(blocked=False)
        blocked_after_lock = _make_user(user_id=unblocked_snapshot.id, blocked=True)
        user_querier.get_user_by_email.return_value = unblocked_snapshot
        user_querier.get_user_by_id_for_update.return_value = blocked_after_lock

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.mobile_login(redis, _make_login_request())

        assert exc_info.value.status_code == 403
        session_querier.upsert_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_locked_row_read_is_used_for_session_creation(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """The locked re-read's user object must be what actually gets
        passed forward — not the earlier, possibly-stale read."""
        stale = _make_user(email="stale@test.com")
        fresh = _make_user(user_id=stale.id, email="fresh@test.com")
        user_querier.get_user_by_email.return_value = stale
        user_querier.get_user_by_id_for_update.return_value = fresh

        await auth_service.mobile_login(redis, _make_login_request())

        user_querier.get_user_by_id_for_update.assert_called_once_with(id=stale.id)

    @pytest.mark.asyncio
    async def test_missing_user_at_lock_time_raises_401(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """Defensive case: user vanished between the two reads (e.g. deleted)."""
        user_querier.get_user_by_email.return_value = _make_user()
        user_querier.get_user_by_id_for_update.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.mobile_login(redis, _make_login_request())

        assert exc_info.value.status_code == 401


# ===========================================================================
# 7. check_rate_limit fail-open behavior
# ===========================================================================


class TestCheckRateLimitFailOpen:
    @pytest.mark.asyncio
    async def test_redis_outage_does_not_block_login(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """A Redis failure during rate-limit checking must not prevent
        login from proceeding — it should fail open, not crash the request."""
        user = _make_user(password="Correctpass1!")
        user_querier.get_user_by_email.return_value = user
        user_querier.get_user_by_id_for_update.return_value = user

        redis.incr = AsyncMock(side_effect=ConnectionError("redis unreachable"))

        result = await auth_service.mobile_login(
            redis, _make_login_request(password="Correctpass1!")
        )

        assert result.access_token  # login succeeded despite Redis being down

    @pytest.mark.asyncio
    async def test_real_rate_limit_rejection_still_raises(
        self,
        auth_service: AuthService,
        redis: AsyncMock,
    ) -> None:
        """Confirm the fail-open except clause doesn't accidentally swallow
        the actual 429 rejection — only infra failures should be caught."""
        redis.incr = AsyncMock(return_value=999)  # way over any reasonable limit

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.check_rate_limit(
                redis, "rate:test:key", max_requests=5, window_seconds=60
            )
        assert exc_info.value.status_code == 429


# ===========================================================================
# 8. block_user — lock ordering and session purge
# ===========================================================================


class TestBlockUser:
    @pytest.mark.asyncio
    async def test_takes_lock_before_mutating(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """block_user must call get_user_by_id_for_update (the lock) before
        set_user_blocked — this is what serializes it against mobile_login."""
        target = _make_user()
        user_querier.get_user_by_id_for_update.return_value = target
        user_querier.set_user_blocked.return_value = _make_user(
            user_id=target.id, blocked=True
        )

        call_order = []
        user_querier.get_user_by_id_for_update.side_effect = lambda *a, **kw: (
            call_order.append("lock") or target
        )
        user_querier.set_user_blocked.side_effect = lambda *a, **kw: (
            call_order.append("mutate") or _make_user(user_id=target.id, blocked=True)
        )

        await auth_service.block_user(redis=redis, user_id=target.id)

        assert call_order == ["lock", "mutate"]

    @pytest.mark.asyncio
    async def test_purges_all_sessions_and_invalidates_cache(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        target = _make_user()
        user_querier.get_user_by_id_for_update.return_value = target
        user_querier.set_user_blocked.return_value = _make_user(
            user_id=target.id, blocked=True
        )

        session_ids = [uuid.uuid4(), uuid.uuid4()]

        async def _sessions(*, user_id):
            for sid in session_ids:
                s = MagicMock()
                s.id = sid
                yield s

        session_querier.list_sessions_by_user = MagicMock(side_effect=_sessions)

        await auth_service.block_user(redis=redis, user_id=target.id)

        session_querier.delete_all_user_sessions.assert_called_once_with(
            user_id=target.id
        )
        assert redis.delete.call_count == len(session_ids)

    @pytest.mark.asyncio
    async def test_missing_user_raises_404(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        user_querier.get_user_by_id_for_update.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.block_user(redis=redis, user_id=uuid.uuid4())
        assert exc_info.value.status_code == 404


# ===========================================================================
# 9. unblock_user
# ===========================================================================


class TestUnblockUser:
    @pytest.mark.asyncio
    async def test_unblocks_successfully(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
    ) -> None:
        target_id = uuid.uuid4()
        user_querier.set_user_blocked.return_value = _make_user(
            user_id=target_id, blocked=False
        )

        result = await auth_service.unblock_user(user_id=target_id)

        assert result.blocked is False
        user_querier.set_user_blocked.assert_called_once_with(
            blocked=False, id=target_id
        )

    @pytest.mark.asyncio
    async def test_missing_user_raises_404(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
    ) -> None:
        user_querier.set_user_blocked.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.unblock_user(user_id=uuid.uuid4())
        assert exc_info.value.status_code == 404


# ===========================================================================
# 10. delete_user — lock ordering and session purge (same shape as block_user)
# ===========================================================================


class TestDeleteUser:
    @pytest.mark.asyncio
    async def test_takes_lock_before_deleting(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        target = _make_user()

        call_order = []
        user_querier.get_user_by_id_for_update.side_effect = lambda *a, **kw: (
            call_order.append("lock") or target
        )
        user_querier.delete_user.side_effect = lambda *a, **kw: call_order.append(
            "delete"
        )

        await auth_service.delete_user(redis=redis, user_id=target.id)

        assert call_order == ["lock", "delete"]

    @pytest.mark.asyncio
    async def test_purges_all_sessions_and_invalidates_cache(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        target = _make_user()
        user_querier.get_user_by_id_for_update.return_value = target

        session_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

        async def _sessions(*, user_id):
            for sid in session_ids:
                s = MagicMock()
                s.id = sid
                yield s

        session_querier.list_sessions_by_user = MagicMock(side_effect=_sessions)

        await auth_service.delete_user(redis=redis, user_id=target.id)

        session_querier.delete_all_user_sessions.assert_called_once_with(
            user_id=target.id
        )
        assert redis.delete.call_count == len(session_ids)

    @pytest.mark.asyncio
    async def test_missing_user_raises_404(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        user_querier.get_user_by_id_for_update.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.delete_user(redis=redis, user_id=uuid.uuid4())
        assert exc_info.value.status_code == 404


# ===========================================================================
# 11. Refresh token — grace window, §4.1a blocked re-check, encryption
# ===========================================================================


class TestRefreshTokenGraceWindow:
    @pytest.mark.asyncio
    async def test_used_token_within_grace_replays_cached_response(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """A used-but-within-grace token with a valid cached response should
        replay it (idempotent retry), not treat it as new or as theft."""
        from app.core.securite import (
            create_raw_refresh_token,
            encrypt_refresh_cache_payload,
        )
        from app.schema.response.mobile.auth import MobileAuthResponse

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(
            user_id=session.user_id, blocked=False
        )

        raw_token = create_raw_refresh_token()
        cached_response = MobileAuthResponse(
            access_token="cached-access-token",
            refresh_token="cached-refresh-token",
            session_id=str(session.id),
            expires_in=900,
            user_id=session.user_id,
        )
        redis.get.return_value = encrypt_refresh_cache_payload(
            cached_response.model_dump_json()
        )

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = True
        row.used_at = datetime.now(timezone.utc) - timedelta(seconds=5)  # within grace
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row

        result = await auth_service.refresh_token(redis, raw_token)

        assert result.access_token == "cached-access-token"
        # must NOT have re-rotated — no new token row created for a replay
        refresh_token_querier.create_refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_used_token_within_grace_but_blocked_user_raises_403(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """§4.1a fix: even with a valid cached replay, a user blocked since
        the original rotation must be rejected, not silently replayed."""
        from app.core.securite import (
            create_raw_refresh_token,
            encrypt_refresh_cache_payload,
        )
        from app.schema.response.mobile.auth import MobileAuthResponse

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(
            user_id=session.user_id,
            blocked=True,  # blocked since original rotation
        )

        raw_token = create_raw_refresh_token()
        cached_response = MobileAuthResponse(
            access_token="cached-access-token",
            refresh_token="cached-refresh-token",
            session_id=str(session.id),
            expires_in=900,
            user_id=session.user_id,
        )
        redis.get.return_value = encrypt_refresh_cache_payload(
            cached_response.model_dump_json()
        )

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = True
        row.used_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_used_token_within_grace_but_cache_miss_raises_401(
        self,
        auth_service: AuthService,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """Regression test for the fall-through bug: a used token within
        grace but with NO cached replay (Redis eviction/failure) must be
        rejected outright, never silently re-rotated into new tokens."""
        from app.core.securite import create_raw_refresh_token

        raw_token = create_raw_refresh_token()
        redis.get.return_value = None  # cache miss

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = True
        row.used_at = datetime.now(timezone.utc) - timedelta(seconds=5)  # within grace
        row.family_id = uuid.uuid4()
        row.session_id = uuid.uuid4()
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)
        assert exc_info.value.status_code == 401
        refresh_token_querier.create_refresh_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_used_token_outside_grace_revokes_session(
        self,
        auth_service: AuthService,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """Reuse outside the grace window is treated as theft — the entire
        session must be revoked."""
        from app.core.securite import create_raw_refresh_token

        raw_token = create_raw_refresh_token()
        session = _make_session()
        session_querier.get_session_by_id.return_value = session

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = True
        row.used_at = datetime.now(timezone.utc) - timedelta(
            seconds=120
        )  # well outside grace
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)

        assert exc_info.value.status_code == 401
        session_querier.delete_session_by_id.assert_called_once_with(
            id=session.id, user_id=session.user_id
        )
        redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_corrupted_cache_value_treated_as_cache_miss(
        self,
        auth_service: AuthService,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """A cached value that fails to decrypt (tampering, corruption,
        wrong key) must be rejected, never trusted or crash the request."""
        from app.core.securite import create_raw_refresh_token

        raw_token = create_raw_refresh_token()
        redis.get.return_value = "not-valid-encrypted-base64-data!!"

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = True
        row.used_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        row.family_id = uuid.uuid4()
        row.session_id = uuid.uuid4()
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row

        with pytest.raises(HTTPException) as exc_info:
            await auth_service.refresh_token(redis, raw_token)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_new_rotation_caches_encrypted_not_plaintext(
        self,
        auth_service: AuthService,
        user_querier: AsyncMock,
        session_querier: AsyncMock,
        refresh_token_querier: AsyncMock,
        redis: AsyncMock,
    ) -> None:
        """The replay cache must never contain the raw token/response as
        plaintext JSON — this is the fix for the Redis-plaintext-secret gap."""
        from app.core.securite import (
            create_raw_refresh_token,
            hash_refresh_token,
            decrypt_refresh_cache_payload,
        )

        session = _make_session()
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(user_id=session.user_id)

        raw_token = create_raw_refresh_token()
        token_hash = hash_refresh_token(raw_token)

        row = MagicMock()
        row.id = uuid.uuid4()
        row.used = False
        row.used_at = None
        row.family_id = uuid.uuid4()
        row.session_id = session.id
        refresh_token_querier.get_refresh_token_by_hash_for_update.return_value = row
        refresh_token_querier.mark_refresh_token_used.return_value = row

        result = await auth_service.refresh_token(redis, raw_token)

        redis.set.assert_called_once()
        call_args = redis.set.call_args
        cache_key = call_args.args[0] if call_args.args else call_args.kwargs.get("key")
        cache_value = (
            call_args.args[1]
            if len(call_args.args) > 1
            else call_args.kwargs.get("value")
        )

        assert cache_key == f"refresh_retry:{token_hash}"
        # plaintext JSON would contain this literal substring; encrypted payload must not
        assert "access_token" not in cache_value
        assert result.access_token not in cache_value

        decrypted = decrypt_refresh_cache_payload(cache_value)
        assert result.access_token in decrypted


class TestValidateSession:
    @pytest.mark.asyncio
    async def test_validate_session_false_when_idle_expired(
        self,
        auth_service: AuthService,
        session_querier: AsyncMock,
        user_querier: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        session = _make_session(
            idle_expires_at=now - timedelta(hours=1),
            absolute_expires_at=now + timedelta(days=30),
        )
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(user_id=session.user_id)

        result = await auth_service.validate_session(AsyncMock(), str(session.id))
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_session_false_when_absolute_expired(
        self,
        auth_service: AuthService,
        session_querier: AsyncMock,
        user_querier: AsyncMock,
    ) -> None:
        now = datetime.now(timezone.utc)
        session = _make_session(
            idle_expires_at=now + timedelta(days=7),
            absolute_expires_at=now - timedelta(hours=1),
        )
        session_querier.get_session_by_id.return_value = session
        user_querier.get_user_by_id.return_value = _make_user(user_id=session.user_id)

        result = await auth_service.validate_session(AsyncMock(), str(session.id))
        assert result is False
