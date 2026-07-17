import uuid
import json
from unittest.mock import AsyncMock, patch, ANY
import pytest

from app.service.users import AuthService
from app.schema.request.mobile.auth import MobileRegisterRequest, RegisterVerifyRequest

@pytest.fixture
def mock_user_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_device_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_session_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_face_embedding_service() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_redis() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def auth_service(
    mock_user_querier: AsyncMock,
    mock_device_querier: AsyncMock,
    mock_session_querier: AsyncMock,
    mock_face_embedding_service: AsyncMock,
) -> AuthService:
    return AuthService(
        user_querier=mock_user_querier,
        device_querier=mock_device_querier,
        session_querier=mock_session_querier,
        face_embedding_service=mock_face_embedding_service,
    )

@pytest.mark.asyncio
@patch("app.service.users.NatsClient.publish")
async def test_mobile_register_sends_otp(
    mock_publish: AsyncMock,
    auth_service: AuthService,
    mock_redis: AsyncMock,
    mock_user_querier: AsyncMock,
) -> None:
    req = MobileRegisterRequest(
        email="test@example.com",
        password="Password1!",
        device_name="iPhone",
        device_type="iOS",
        physical_device_id=uuid.uuid4(),
    )
    mock_user_querier.get_user_by_email.return_value = None
    mock_redis.incr.return_value = 1

    res = await auth_service.mobile_register(redis=mock_redis, req=req)

    assert res.status == "pending_verification"
    assert res.email == "test@example.com"
    assert mock_redis.set.call_count == 2

    mock_publish.assert_called_once()
    args, _ = mock_publish.call_args
    assert args[0] == "email.send_otp"
    payload = json.loads(args[1])
    assert payload["email"] == "test@example.com"
    assert "otp" in payload

@pytest.mark.asyncio
async def test_verify_mobile_register_success(
    auth_service: AuthService,
    mock_redis: AsyncMock,
    mock_user_querier: AsyncMock,
    mock_device_querier: AsyncMock,
    mock_session_querier: AsyncMock,
) -> None:
    device_id = uuid.uuid4()
    req = RegisterVerifyRequest(
        email="test@example.com",
        password="Password1!",
        device_name="iPhone",
        device_type="iOS",
        physical_device_id=device_id,
        otp="123456"
    )

    mock_redis.get.side_effect = [
        "123456",
        json.dumps({"hashed_password": "hashed_pass"})
    ]

    mock_user = AsyncMock()
    mock_user.id = uuid.uuid4()
    mock_user.email = "test@example.com"
    mock_user.blocked = False
    mock_user_querier.create_user.return_value = mock_user

    mock_session_querier.count_user_sessions.return_value = 0
    mock_session = AsyncMock()
    mock_session.id = uuid.uuid4()
    mock_session_querier.upsert_session.return_value = mock_session

    # FIX 1: Mock the new lookup method to return None (device not found)
    mock_device_querier.get_device_by_physical_id.return_value = None
    # FIX 2: Mock create_device to return a truthy device
    mock_device_querier.create_device.return_value = AsyncMock()

    with patch("app.service.users.SessionService.cache_session_for_auth", new_callable=AsyncMock):
        res = await auth_service.verify_mobile_register(redis=mock_redis, req=req)

    assert res.is_new_user is True
    assert res.user_id == mock_user.id
    mock_user_querier.create_user.assert_called_once_with(email="test@example.com", hashed_password="hashed_pass")
    assert mock_redis.delete.call_count == 2

@pytest.mark.asyncio
async def test_mobile_register_resend_otp_success(
    auth_service: AuthService,
    mock_redis: AsyncMock,
) -> None:
    email = "test@example.com"
    mock_redis.get.return_value = '{"hashed_password": "fake"}'
    mock_redis.incr.return_value = 1

    with patch("app.service.users.NatsClient.publish", new_callable=AsyncMock) as mock_publish:
        res = await auth_service.mobile_register_resend_otp(redis=mock_redis, email=email)

    assert res.status == "pending_verification"
    assert res.message == "New OTP sent to email"
    assert res.email == email
    mock_redis.get.assert_called_with(f"pending_user:{email}")
    mock_redis.set.assert_called_with(f"otp:{email}", ANY, expire=600)
    mock_publish.assert_called_once()

@pytest.mark.asyncio
async def test_mobile_register_resend_otp_not_found(
    auth_service: AuthService,
    mock_redis: AsyncMock,
) -> None:
    from fastapi import HTTPException
    email = "test@example.com"
    mock_redis.incr.return_value = 1
    mock_redis.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.mobile_register_resend_otp(redis=mock_redis, email=email)

    assert exc_info.value.status_code == 404
    assert "No pending registration found" in exc_info.value.detail