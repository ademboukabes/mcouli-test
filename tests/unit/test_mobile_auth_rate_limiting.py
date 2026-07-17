import asyncio
import uuid
from typing import Any

import pytest
from fastapi import HTTPException
from app.service.users import AuthService
from app.schema.request.mobile.auth import MobileLoginRequest

# Test doubles intentionally implement only the AuthService methods exercised here.
# They do not subclass the generated queriers, so mypy would otherwise flag each
# constructor injection as an arg-type mismatch.
# mypy: disable-error-code=arg-type


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True


class FakeUser:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.email = "test@example.com"
        from app.core.securite import hash_password
        self.hashed_password = hash_password("ValidPass@123")
        self.blocked = False


class FakeUserQuerier:
    async def get_user_by_email(self, email: str) -> FakeUser:
        return FakeUser()


class FakeDeviceQuerier:
    pass


class FakeSessionQuerier:
    pass


class FakeFaceEmbeddingService:
    pass


def test_rate_limiting_triggered_after_max_attempts() -> None:
    # Set up mocks
    redis = MockRedis()
    service = AuthService(
        user_querier=FakeUserQuerier(),
        device_querier=FakeDeviceQuerier(),
        session_querier=FakeSessionQuerier(),
        face_embedding_service=FakeFaceEmbeddingService(),
    )

    # Stub session creation to avoid database / redis dependencies
    async def _dummy_create_session(*args: object, **kwargs: object) -> Any:
        from app.schema.response.mobile.auth import MobileAuthResponse
        return MobileAuthResponse(
            access_token="access",
            refresh_token="refresh",
            session_id=str(uuid.uuid4()),
            expires_in=3600,
            user_id=uuid.uuid4(),
            is_new_user=False,
        )
    service._create_mobile_session = _dummy_create_session  # type: ignore

    req = MobileLoginRequest(
        email="test@example.com",
        password="ValidPass@123",
        device_name="Pixel 8",
        device_type="android",
        physical_device_id=uuid.uuid4(),
    )

    # Call mobile_login 5 times (which is the default max limit in settings)
    # The first 5 should succeed without raising exceptions
    for i in range(5):
        res = asyncio.run(service.mobile_login(redis, req, client_ip="127.0.0.1"))
        assert res.access_token == "access"

    # The 6th call must trigger the rate limit and raise 429!
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(service.mobile_login(redis, req, client_ip="127.0.0.1"))
    assert exc_info.value.status_code == 429
    assert "too many requests" in exc_info.value.detail.lower()

    # The ttls for the keys should have been set
    assert redis.ttls["rate:ip:127.0.0.1"] == 60
    assert redis.ttls["rate:email:test@example.com"] == 60
