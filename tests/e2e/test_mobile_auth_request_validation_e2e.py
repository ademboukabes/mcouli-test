import os
import uuid

import httpx
import pytest


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.getenv("MULTAI_RUN_E2E") != "1",
        reason="set MULTAI_RUN_E2E=1 to run live e2e tests",
    ),
]


BASE_URL = os.getenv("MULTAI_E2E_BASE_URL", "http://localhost:8000").rstrip("/")
REGISTER_URL = f"{BASE_URL}/user/auth/register"
LOGIN_URL = f"{BASE_URL}/user/auth/login"


def _valid_payload() -> dict[str, object]:
    return {
        "email": f"e2e-{uuid.uuid4()}@example.com",
        "password": "ValidPass@123",
        "device_name": "Pixel 8",
        "device_type": "android",
        "device_id": str(uuid.uuid4()),
    }


@pytest.mark.parametrize("field", ["password", "device_name", "device_type"])
@pytest.mark.parametrize("value", ["", "   "])
@pytest.mark.parametrize("url", [REGISTER_URL, LOGIN_URL])
def test_live_register_login_rejects_empty_required_text_fields(
    field: str,
    value: str,
    url: str,
) -> None:
    payload = _valid_payload()
    payload[field] = value

    headers = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 250 + 1}"}
    response = httpx.post(url, json=payload, headers=headers, timeout=10.0)

    assert response.status_code == 422


@pytest.mark.parametrize("url", [REGISTER_URL, LOGIN_URL])
def test_live_register_login_rejects_padded_short_password(url: str) -> None:
    payload = _valid_payload()
    payload["password"] = "       a"

    headers = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 250 + 1}"}
    response = httpx.post(url, json=payload, headers=headers, timeout=10.0)

    assert response.status_code == 422
