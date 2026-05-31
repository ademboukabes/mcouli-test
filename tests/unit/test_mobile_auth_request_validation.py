import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.container import get_container
from app.main import app
from app.schema.request.mobile.auth import MobileAuthRequest
from app.schema.response.mobile.auth import MobileAuthResponse


class FakeAuthService:
    def __init__(self) -> None:
        self.received_request: MobileAuthRequest | None = None

    async def mobile_register_login(
        self,
        redis: object,
        req: MobileAuthRequest,
    ) -> MobileAuthResponse:
        self.received_request = req
        return MobileAuthResponse(
            access_token="access",
            refresh_token="refresh",
            session_id=str(uuid.uuid4()),
            expires_in=3600,
            user_id=uuid.uuid4(),
            is_new_user=True,
        )


class FakeAuditService:
    async def create_record(self, **kwargs: Any) -> None:
        return None


class FakeContainer:
    def __init__(self) -> None:
        self.redis = object()
        self.auth_service = FakeAuthService()
        self.audit_service = FakeAuditService()


@pytest.fixture
def fake_container() -> FakeContainer:
    return FakeContainer()


@pytest.fixture
def client(fake_container: FakeContainer) -> Iterator[TestClient]:
    app.dependency_overrides[get_container] = lambda: fake_container
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _valid_payload() -> dict[str, object]:
    return {
        "email": "USER@Example.COM",
        "password": "validpass123",
        "device_name": "Pixel 8",
        "device_type": "android",
        "device_id": str(uuid.uuid4()),
    }


@pytest.mark.parametrize("field", ["password", "device_name", "device_type"])
@pytest.mark.parametrize("value", ["", "   "])
def test_register_login_rejects_empty_required_text_fields(
    client: TestClient,
    fake_container: FakeContainer,
    field: str,
    value: str,
) -> None:
    payload = _valid_payload()
    payload[field] = value

    response = client.post("/user/auth/register-login", json=payload)

    assert response.status_code == 422
    assert fake_container.auth_service.received_request is None


def test_register_login_passes_normalized_input_to_service(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    payload = _valid_payload()
    payload.update(
        {
            "email": " USER@Example.COM ",
            "device_name": " Pixel 8 ",
            "device_type": " ANDROID ",
        }
    )

    response = client.post("/user/auth/register-login", json=payload)

    assert response.status_code == 200
    req = fake_container.auth_service.received_request
    assert req is not None
    assert req.email == "user@example.com"
    assert req.device_name == "Pixel 8"
    assert req.device_type == "android"


def test_register_login_password_length_is_checked_after_trimming(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    payload = _valid_payload()
    payload["password"] = "       a"

    response = client.post("/user/auth/register-login", json=payload)

    assert response.status_code == 422
    assert fake_container.auth_service.received_request is None
