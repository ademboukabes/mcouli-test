from collections.abc import AsyncIterator
from typing import Any

# Test doubles intentionally implement only the AuthService methods exercised here.
# They do not subclass the generated queriers, so mypy would otherwise flag each
# constructor injection as an arg-type mismatch.
# mypy: disable-error-code=arg-type

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import app.service.users as users_module
from app.core.securite import hash_password
from app.schema.request.mobile.auth import MobileLoginRequest, MobileRegisterRequest, RegisterVerifyRequest
from app.service.session import SessionService
from app.service.users import AuthService


class FakeUser:
    def __init__(self, email: str, exists: bool = True, password: str = "ValidPass@123") -> None:
        self.id = uuid.uuid4()
        self.email = email
        self.blocked = False
        self.hashed_password = hash_password(password)
        self.exists = exists


class FakeDevice:
    def __init__(self, physical_device_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.id = uuid.uuid4()
        self.physical_device_id = physical_device_id
        self.user_id = user_id
        self.is_invalid_token = False
        self.is_active = True


class FakeSession:
    def __init__(self, user_id: uuid.UUID, device_id: uuid.UUID) -> None:
        self.id = uuid.uuid4()
        self.user_id = user_id
        self.device_id = device_id
        self.expires_at = datetime.now(timezone.utc)
        self.last_active = datetime.now(timezone.utc)
        self.created_at = datetime.now(timezone.utc)


class FakeUserQuerier:
    def __init__(self, user: FakeUser) -> None:
        self._user = user
        self._created_users: dict[str, FakeUser] = {}

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        if self._user.exists and self._user.email == email:
            return self._user
        if email in self._created_users:
            return self._created_users[email]
        return None

    async def get_user_by_id(self, id: uuid.UUID) -> FakeUser | None:
        if self._user.id == id:
            return self._user
        return None

    async def create_user(self, *, email: str, hashed_password: str) -> FakeUser:
        new_user = FakeUser(email=email, exists=True)
        new_user.hashed_password = hashed_password
        self._created_users[email] = new_user
        return new_user


class FakeDeviceQuerier:
    """Stateful fake — tracks devices keyed by (user_id, physical_device_id),
    matching the real UNIQUE(user_id, physical_device_id) constraint."""

    def __init__(self) -> None:
        self._devices: dict[tuple[uuid.UUID, uuid.UUID], FakeDevice] = {}

    async def get_device_by_physical_id(
        self, *, user_id: uuid.UUID, physical_device_id: uuid.UUID
    ) -> FakeDevice | None:
        return self._devices.get((user_id, physical_device_id))

    async def get_device_by_id_any(self, id: uuid.UUID) -> FakeDevice | None:
        # Kept only because the generated querier exposes it; application code
        # no longer calls this for auth decisions.
        return None

    async def get_device_by_id(self, id: uuid.UUID, user_id: uuid.UUID) -> FakeDevice | None:
        for device in self._devices.values():
            if device.id == id and device.user_id == user_id:
                return device
        return None

    async def create_device(self, arg: Any) -> FakeDevice:
        device = FakeDevice(physical_device_id=arg.physical_device_id, user_id=arg.user_id)
        self._devices[(arg.user_id, arg.physical_device_id)] = device
        return device

    async def activate_device(self, id: uuid.UUID, user_id: uuid.UUID) -> None:
        return None


class FakeSessionQuerier:
    """Stateful fake — tracks sessions keyed by (user_id, device_id), matching
    the real UNIQUE(user_id, device_id) constraint and upsert-on-conflict
    behavior."""

    def __init__(self) -> None:
        self._sessions: dict[tuple[uuid.UUID, uuid.UUID], FakeSession] = {}

    async def get_session_by_device_for_user(
        self, *, device_id: uuid.UUID, user_id: uuid.UUID
    ) -> FakeSession | None:
        return self._sessions.get((user_id, device_id))

    async def get_session_by_id(self, id: uuid.UUID) -> FakeSession | None:
        for session in self._sessions.values():
            if session.id == id:
                return session
        return None

    async def list_sessions_by_user(self, user_id: uuid.UUID) -> AsyncIterator[FakeSession]:
        for (u, _d), session in self._sessions.items():
            if u == user_id:
                yield session

    async def delete_session_by_id(self, *, id: uuid.UUID, user_id: uuid.UUID) -> None:
        key_to_remove = None
        for key, session in self._sessions.items():
            if session.id == id and session.user_id == user_id:
                key_to_remove = key
                break
        if key_to_remove:
            del self._sessions[key_to_remove]

    async def lock_user_sessions(self, *, user_id: str) -> None:
        return None

    async def evict_overflow_sessions(
        self, *, user_id: uuid.UUID, id: uuid.UUID, session_limit: int
    ) -> AsyncIterator[uuid.UUID]:
        candidates = [
            s for (u, _d), s in list(self._sessions.items())
            if u == user_id and s.id != id
        ]
        # +1 accounts for the current session itself, which isn't in `candidates`
        # but does count toward the real COUNT(*) the SQL version computes.
        overflow = max(0, (len(candidates) + 1) - session_limit)
        candidates.sort(key=lambda s: (s.last_active, s.created_at))
        for s in candidates[:overflow]:
            key = next(k for k, v in self._sessions.items() if v is s)
            del self._sessions[key]
            yield s.id

    async def upsert_session(
        self,
        *,
        user_id: uuid.UUID,
        device_id: uuid.UUID,
        expires_at: datetime,
    ) -> FakeSession:
        key = (user_id, device_id)
        existing = self._sessions.get(key)
        if existing:
            existing.expires_at = expires_at
            existing.last_active = datetime.now(timezone.utc)
            return existing
        session = FakeSession(user_id=user_id, device_id=device_id)
        session.expires_at = expires_at
        self._sessions[key] = session
        return session

class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def incr(self, key: str) -> int:
        current = int(self._store.get(key, "0")) + 1
        self._store[key] = str(current)
        return current

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ttl(self, key: str) -> int:
        return -1

    async def set(self, key: str, value: str, expire: int) -> None:
        self._store[key] = value

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class FakeFaceEmbeddingService:
    pass


def _patch_token_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)


def test_login_with_unknown_email_is_rejected() -> None:
    """Test that login with unknown email fails."""
    user = FakeUser(email="user@example.com", exists=True)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="unknown@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_login(FakeRedis(), req))
    assert exc_info.value.status_code == 401
    assert "not found" in exc_info.value.detail.lower()


def test_register_with_existing_email_is_rejected() -> None:
    """Test that registration with existing email fails."""
    user = FakeUser(email="user@example.com", exists=True)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_register(FakeRedis(), req))
    assert exc_info.value.status_code == 409
    assert "already" in exc_info.value.detail.lower()


def test_login_with_correct_credentials_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that login with correct credentials succeeds."""
    user = FakeUser(email="user@example.com", exists=True)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    _patch_token_helpers(monkeypatch)

    result = asyncio.run(service.mobile_login(FakeRedis(), req))
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"
    assert result.is_new_user is False


def test_register_with_new_email_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that registration with new email succeeds."""
    user = FakeUser(email="user@example.com", exists=False)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="newuser@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    _patch_token_helpers(monkeypatch)

    result = asyncio.run(service.mobile_register(FakeRedis(), req))
    assert result.status == "pending_verification"


def test_register_then_login_same_device_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test full flow: register then login with same device."""
    user = FakeUser(email="newuser@example.com", exists=False)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    _patch_token_helpers(monkeypatch)

    physical_device_id = uuid.uuid4()
    password = "ValidPass@123"

    register_req = MobileRegisterRequest(
        email="newuser@example.com",
        password=password,
        device_name="TestDevice",
        device_type="android",
        physical_device_id=physical_device_id,
    )
    fake_redis = FakeRedis()
    result1 = asyncio.run(service.mobile_register(fake_redis, register_req))
    assert result1.status == "pending_verification"

    verify_req = RegisterVerifyRequest(
        email="newuser@example.com",
        password=password,
        otp="123456",
        device_name="TestDevice",
        device_type="android",
        physical_device_id=physical_device_id,
    )
    fake_redis._store["otp:newuser@example.com"] = "123456"
    fake_redis._store["pending_user:newuser@example.com"] = json.dumps(
        {"hashed_password": hash_password(password)}
    )

    verify_result = asyncio.run(service.verify_mobile_register(fake_redis, verify_req))
    assert verify_result.is_new_user is True

    login_req = MobileLoginRequest(
        email="newuser@example.com",
        password=password,
        device_name="TestDevice",
        device_type="android",
        physical_device_id=physical_device_id,
    )
    result2 = asyncio.run(service.mobile_login(FakeRedis(), login_req))
    assert result2.is_new_user is False


def test_login_with_wrong_password_fails() -> None:
    """Test that login with wrong password fails."""
    user = FakeUser(email="user@example.com", exists=True)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="user@example.com",
        password="wrongpassword",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_login(FakeRedis(), req))
    assert exc_info.value.status_code == 401
    assert "invalid" in exc_info.value.detail.lower()


def test_login_logs_correctly(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that login emits audit-friendly logs without email."""
    caplog.set_level(logging.INFO, logger="multAI")

    user = FakeUser(email="user@example.com", exists=True)
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="USER@Example.COM",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    _patch_token_helpers(monkeypatch)

    asyncio.run(service.mobile_login(FakeRedis(), req))

    assert "mobile_login attempt" in caplog.text
    assert "login success user_id=" in caplog.text
    assert "session_id=" in caplog.text
    assert "user@example.com" not in caplog.text


def test_register_concurrent_signup_integrity_error() -> None:
    """Test that concurrent signup IntegrityError is caught and raised as 409."""
    from sqlalchemy.exc import IntegrityError

    class FakeOrigException(Exception):
        sqlstate = "23505"
        constraint_name = "idx_users_email"

    user = FakeUser(email="user@example.com", exists=False)

    async def _raise_integrity_error(*args: Any, **kwargs: Any) -> Any:
        raise IntegrityError(
            statement="INSERT INTO users",
            params={},
            orig=FakeOrigException("duplicate key value violates unique constraint idx_users_email")
        )

    user_querier = FakeUserQuerier(user)
    user_querier.create_user = _raise_integrity_error  # type: ignore

    service = AuthService(
        user_querier=user_querier,
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    verify_req = RegisterVerifyRequest(
        email="newuser@example.com",
        password="ValidPass@123",
        otp="123456",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    fake_redis = FakeRedis()
    fake_redis._store["otp:newuser@example.com"] = "123456"
    fake_redis._store["pending_user:newuser@example.com"] = json.dumps(
        {"hashed_password": hash_password("ValidPass@123")}
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.verify_mobile_register(fake_redis, verify_req))

    assert exc_info.value.status_code == 409
    assert "already in use" in exc_info.value.detail.lower()


# ===========================================================================
# Regression tests — Phase 2 bug fixes
# ===========================================================================


def test_session_device_id_matches_surrogate_pk_not_physical_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for the FK bug: user_sessions.device_id must be the
    device row's surrogate id, never the client-supplied physical_device_id
    directly. Pre-migration these happened to be equal by construction;
    post-migration they are unrelated UUIDs."""
    user = FakeUser(email="user@example.com", exists=True)
    device_querier = FakeDeviceQuerier()
    session_querier = FakeSessionQuerier()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=device_querier,
        session_querier=session_querier,
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    physical_id = uuid.uuid4()
    req = MobileLoginRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=physical_id,
    )

    _patch_token_helpers(monkeypatch)

    asyncio.run(service.mobile_login(FakeRedis(), req))

    assert len(device_querier._devices) == 1
    device = next(iter(device_querier._devices.values()))
    assert len(session_querier._sessions) == 1
    session = next(iter(session_querier._sessions.values()))

    assert session.device_id == device.id
    assert session.device_id != physical_id


def test_relogin_on_existing_device_succeeds_even_at_session_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for the session-cap-vs-replace bug: a user at the
    session cap must still be able to re-login on a device they already
    have an active session on (replace), while a genuinely new device
    should evict the oldest and succeed (Phase 4 behavior)."""
    user = FakeUser(email="user@example.com", exists=True)
    device_querier = FakeDeviceQuerier()
    session_querier = FakeSessionQuerier()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=device_querier,
        session_querier=session_querier,
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    _patch_token_helpers(monkeypatch)

    # Fill up the cap with sessions on distinct devices.
    for i in range(AuthService.SESSION_LIMIT):
        other_req = MobileLoginRequest(
            email="user@example.com",
            password="ValidPass@123",
            device_name=f"Device {i}",
            device_type="android",
            physical_device_id=uuid.uuid4(),
        )
        asyncio.run(service.mobile_login(FakeRedis(), other_req))

    assert len(session_querier._sessions) == AuthService.SESSION_LIMIT

    # A genuinely NEW device at the cap should evict the oldest and SUCCEED.
    result = asyncio.run(service.mobile_login(FakeRedis(), MobileLoginRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="New device",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )))
    assert result.access_token == "access"
    # Count stays at cap — one evicted, one added.
    assert len(session_querier._sessions) == AuthService.SESSION_LIMIT

    # Re-logging in on an EXISTING device (replace) must still succeed.
    existing_physical_id = next(iter(device_querier._devices.values())).physical_device_id
    repeat_req = MobileLoginRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Device 0",
        device_type="android",
        physical_device_id=existing_physical_id,
    )
    result = asyncio.run(service.mobile_login(FakeRedis(), repeat_req))
    assert result.access_token == "access"
    # Session count must NOT have grown — this was a replace, not an addition.
    assert len(session_querier._sessions) == AuthService.SESSION_LIMIT

def test_same_physical_device_id_reuses_device_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two logins with the same (user, physical_device_id) must reuse the
    same device row, never create a duplicate."""
    user = FakeUser(email="user@example.com", exists=True)
    device_querier = FakeDeviceQuerier()
    session_querier = FakeSessionQuerier()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=device_querier,
        session_querier=session_querier,
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    _patch_token_helpers(monkeypatch)

    physical_id = uuid.uuid4()

    for _ in range(3):
        req = MobileLoginRequest(
            email="user@example.com",
            password="ValidPass@123",
            device_name="Pixel 8",
            device_type="android",
            physical_device_id=physical_id,
        )
        asyncio.run(service.mobile_login(FakeRedis(), req))

    assert len(device_querier._devices) == 1
    assert len(session_querier._sessions) == 1
