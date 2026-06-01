import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.container import get_container
from app.main import app
from app.schema.request.mobile.auth import MobileLoginRequest, MobileRegisterRequest
from app.schema.response.mobile.auth import MobileAuthResponse


class FakeAuthService:
    def __init__(self) -> None:
        self.register_request: MobileRegisterRequest | None = None
        self.login_request: MobileLoginRequest | None = None
        self.register_client_ip: object = None
        self.login_client_ip: object = None

    async def mobile_register(
        self,
        redis: object,
        req: MobileRegisterRequest,
        client_ip: object = None,
    ) -> MobileAuthResponse:
        self.register_request = req
        self.register_client_ip = client_ip
        return MobileAuthResponse(
            access_token="access",
            refresh_token="refresh",
            session_id=str(uuid.uuid4()),
            expires_in=3600,
            user_id=uuid.uuid4(),
            is_new_user=True,
        )

    async def mobile_login(
        self,
        redis: object,
        req: MobileLoginRequest,
        client_ip: object = None,
    ) -> MobileAuthResponse:
        self.login_request = req
        self.login_client_ip = client_ip
        return MobileAuthResponse(
            access_token="access",
            refresh_token="refresh",
            session_id=str(uuid.uuid4()),
            expires_in=3600,
            user_id=uuid.uuid4(),
            is_new_user=False,
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
        "password": "ValidPass@123",
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
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        payload[field] = value

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
        assert getattr(fake_container.auth_service, attr) is None


def test_register_login_passes_normalized_input_to_service(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        payload.update(
            {
                "email": " USER@Example.COM ",
                "device_name": " Pixel 8 ",
                "device_type": " ANDROID ",
            }
        )

        response = client.post(endpoint, json=payload)

        assert response.status_code == 200
        req = getattr(fake_container.auth_service, attr)
        assert req is not None
        assert req.email == "user@example.com"
        assert req.device_name == "Pixel 8"
        assert req.device_type == "android"


def test_register_login_password_length_is_checked_after_trimming(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        payload["password"] = "       a"

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
        assert getattr(fake_container.auth_service, attr) is None


def test_register_login_rejects_oversized_email(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        # Create an email address with a length > 255 chars
        # username part is 250 'a's, domain is "@example.com"
        payload["email"] = "a" * 250 + "@example.com"

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
        assert getattr(fake_container.auth_service, attr) is None


def test_register_enforces_password_complexity(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    # Valid complex password
    payload = _valid_payload()
    payload["password"] = "P@ssword123"
    response = client.post("/user/auth/register", json=payload)
    assert response.status_code == 200
    assert fake_container.auth_service.register_request is not None

    # Invalid passwords lacking different criteria
    invalid_passwords = [
        "p@ssword123",  # missing uppercase
        "P@SSWORD123",  # missing lowercase
        "P@sswordabc",  # missing digit
        "Password123",  # missing special char
    ]
    for pw in invalid_passwords:
        fake_container.auth_service.register_request = None
        payload = _valid_payload()
        payload["password"] = pw
        response = client.post("/user/auth/register", json=payload)
        assert response.status_code == 422
        assert fake_container.auth_service.register_request is None


def test_login_does_not_enforce_password_complexity(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    # Simple password should still be allowed to attempt log in
    payload = _valid_payload()
    payload["password"] = "Password123"  # missing special character
    response = client.post("/user/auth/login", json=payload)
    assert response.status_code == 200
    assert fake_container.auth_service.login_request is not None


def test_mobile_auth_uses_forwarded_ip_for_rate_limit_identity(
    client: TestClient,
    fake_container: FakeContainer,
) -> None:
    payload = _valid_payload()

    response = client.post(
        "/user/auth/login",
        json=payload,
        headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.1"},
    )

    assert response.status_code == 200
    assert fake_container.auth_service.login_client_ip == "203.0.113.10"


