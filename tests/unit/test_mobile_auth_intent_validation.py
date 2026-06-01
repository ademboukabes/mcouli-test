from typing import Any

# Test doubles intentionally implement only the AuthService methods exercised here.
# They do not subclass the generated queriers, so mypy would otherwise flag each
# constructor injection as an arg-type mismatch.
# mypy: disable-error-code=arg-type

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

import app.service.users as users_module
from app.core.securite import hash_password
from app.schema.request.mobile.auth import MobileLoginRequest, MobileRegisterRequest
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
    is_invalid_token = False
    is_active = True


class FakeSession:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.expires_at = datetime.now(timezone.utc)


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
    async def get_device_by_id(self, id: uuid.UUID) -> FakeDevice | None:
        return None

    async def create_device(self, arg: object) -> FakeDevice:
        return FakeDevice()

    async def activate_device(self, id: uuid.UUID, user_id: uuid.UUID) -> None:
        return None


class FakeSessionQuerier:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        return 0

    async def get_session_by_id(self, id: uuid.UUID) -> FakeSession | None:
        return self._session

    async def upsert_session(
        self,
        *,
        user_id: uuid.UUID,
        device_id: uuid.UUID,
        expires_at: datetime,
    ) -> FakeSession:
        self._session.expires_at = expires_at
        return self._session


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ttl(self, key: str) -> int:
        return -1

    async def set(self, key: str, value: str, expire: int) -> None:
        return None


class FakeFaceEmbeddingService:
    pass


def test_login_with_unknown_email_is_rejected() -> None:
    """Test that login with unknown email fails."""
    user = FakeUser(email="user@example.com", exists=True)
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="unknown@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_login(FakeRedis(), req))
    assert exc_info.value.status_code == 401
    assert "not found" in exc_info.value.detail.lower()


def test_register_with_existing_email_is_rejected() -> None:
    """Test that registration with existing email fails."""
    user = FakeUser(email="user@example.com", exists=True)
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
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
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="user@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )

    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)

    result = asyncio.run(service.mobile_login(FakeRedis(), req))
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"
    assert result.is_new_user is False


def test_register_with_new_email_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that registration with new email succeeds."""
    user = FakeUser(email="user@example.com", exists=False)
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="newuser@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )

    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)

    result = asyncio.run(service.mobile_register(FakeRedis(), req))
    assert result.access_token == "access"
    assert result.refresh_token == "refresh"
    assert result.is_new_user is True


def test_register_then_login_same_device_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test full flow: register then login with same device."""
    user = FakeUser(email="newuser@example.com", exists=False)
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)

    device_id = uuid.uuid4()
    password = "ValidPass@123"

    # Register
    register_req = MobileRegisterRequest(
        email="newuser@example.com",
        password=password,
        device_name="TestDevice",
        device_type="android",
        device_id=device_id,
    )
    result1 = asyncio.run(service.mobile_register(FakeRedis(), register_req))
    assert result1.is_new_user is True

    # Try to register again (should fail)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_register(FakeRedis(), register_req))
    assert exc_info.value.status_code == 409

    # Now login
    login_req = MobileLoginRequest(
        email="newuser@example.com",
        password=password,
        device_name="TestDevice",
        device_type="android",
        device_id=device_id,
    )
    result2 = asyncio.run(service.mobile_login(FakeRedis(), login_req))
    assert result2.is_new_user is False


def test_login_with_wrong_password_fails() -> None:
    """Test that login with wrong password fails."""
    user = FakeUser(email="user@example.com", exists=True)
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="user@example.com",
        password="wrongpassword",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
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
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileLoginRequest(
        email="USER@Example.COM",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )

    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)

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
    session = FakeSession()

    async def _raise_integrity_error(*args: Any, **kwargs: Any) -> Any:
        raise IntegrityError(
            statement="INSERT INTO users",
            params={},
            orig=FakeOrigException("duplicate key value violates unique constraint idx_users_email")
        )

    user_querier = FakeUserQuerier(user)
    # Stub create_user to raise IntegrityError
    user_querier.create_user = _raise_integrity_error  # type: ignore

    service = AuthService(
        user_querier=user_querier,
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="newuser@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_register(FakeRedis(), req))

    assert exc_info.value.status_code == 409
    assert "already in use" in exc_info.value.detail.lower()

