# Test doubles intentionally implement only the AuthService methods exercised here.
# They do not subclass the generated queriers, so mypy would otherwise flag each
# constructor injection as an arg-type mismatch.
# mypy: disable-error-code=arg-type

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import pytest

import app.service.users as users_module
from app.schema.request.mobile.auth import MobileRegisterRequest
from app.service.session import SessionService
from app.service.users import AuthService


class FakeUser:
    def __init__(self, email: str) -> None:
        self.id = uuid.uuid4()
        self.email = email
        self.blocked = False
        self.hashed_password = "hashed"


class FakeDevice:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.is_invalid_token = False
        self.is_active = True


class FakeSession:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.expires_at = datetime.now(timezone.utc)


class FakeUserQuerier:
    def __init__(self, user: FakeUser) -> None:
        self._user = user

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        return None

    async def create_user(self, *, email: str, hashed_password: str) -> FakeUser:
        self._user.email = email
        self._user.hashed_password = hashed_password
        return self._user


class FakeDeviceQuerier:
    async def get_device_by_physical_id(
        self, *, user_id: uuid.UUID, physical_device_id: uuid.UUID
    ) -> FakeDevice | None:
        return None

    async def get_device_by_id_any(self, id: uuid.UUID) -> FakeDevice | None:
        return None

    async def get_device_by_id(self, id: uuid.UUID) -> FakeDevice | None:
        return None

    async def create_device(self, arg: object) -> FakeDevice:
        return FakeDevice()


class FakeSessionQuerier:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        return 0

    async def get_session_by_device_for_user(
        self, *, device_id: uuid.UUID, user_id: uuid.UUID
    ) -> FakeSession | None:
        return None

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


def test_mobile_register_logs_without_plaintext_email(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that plaintext email is never logged; use user_id instead."""
    caplog.set_level(logging.INFO, logger="multAI")

    user = FakeUser(email="user@example.com")
    session = FakeSession()
    service = AuthService(
        user_querier=FakeUserQuerier(user),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(session),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    req = MobileRegisterRequest(
        email="USER@Example.COM",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    async def _noop_cache_session_for_auth(**_: object) -> None:
        return None

    monkeypatch.setattr(SessionService, "cache_session_for_auth", _noop_cache_session_for_auth)
    monkeypatch.setattr(users_module, "create_acces_mobile_token", lambda _: "access")
    monkeypatch.setattr(users_module, "create_refresh_mobile_token", lambda _: "refresh")
    monkeypatch.setattr(users_module, "Get_expiry_time", lambda: 3600)

    asyncio.run(service.mobile_register(FakeRedis(), req))

    # Verify no plaintext email in logs
    assert req.email not in caplog.text
    assert "user@example.com" not in caplog.text
    assert "mobile_register attempt" in caplog.text
