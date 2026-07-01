import os
import uuid
import requests  # type: ignore[import-untyped]
import pytest


@pytest.mark.skipif(
    not os.getenv("MULTAI_RUN_E2E"),
    reason="E2E disabled (set MULTAI_RUN_E2E=1 to run)",
)
class TestMobileAuthEndpointsE2E:
    """End-to-end tests for mobile auth register/login endpoints.

    These tests run against a live API. Set MULTAI_RUN_E2E=1 and
    MULTAI_E2E_BASE_URL=http://localhost:8000 to enable.
    """

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.base_url = os.getenv("MULTAI_E2E_BASE_URL", "http://localhost:8000")
        self.headers = {
            "X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 250 + 1}",
        }

    def test_login_with_unknown_email_fails(self) -> None:
        """Test that login with unknown email returns 401."""
        payload = {
            "email": f"nonexistent_{uuid.uuid4()}@example.com",
            "password": "anypassword",
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": str(uuid.uuid4()),
        }
        response = requests.post(
            f"{self.base_url}/user/auth/login",
            json=payload,
            headers=self.headers,
        )
        assert response.status_code == 401
        assert "not found" in response.json()["detail"].lower()

    def test_register_with_existing_email_fails(self) -> None:
        """Test that registration with existing email returns 409."""
        email = f"testuser_{uuid.uuid4()}@example.com"
        device_id = str(uuid.uuid4())

        # First registration succeeds
        register_payload = {
            "email": email,
            "password": "ValidPass@123",
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        response1 = requests.post(
            f"{self.base_url}/user/auth/register",
            json=register_payload,
            headers=self.headers,
        )
        assert response1.status_code == 200
        assert response1.json()["status"] == "pending_verification"

        # Second registration with same email should also succeed and resend OTP
        # Wait, if they are still pending, it just overwrites the pending data.
        # But if they are FULLY registered, it returns 409.
        # Let's verify them first to fully register them.
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        otp = r.get(f"otp:{email}")
        
        verify_payload = {
            "email": email,
            "password": "ValidPass@123",
            "otp": otp,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        verify_response = requests.post(
            f"{self.base_url}/user/auth/register/verify",
            json=verify_payload,
            headers=self.headers,
        )
        assert verify_response.status_code == 200

        # Now second registration with same email fails
        response2 = requests.post(
            f"{self.base_url}/user/auth/register",
            json=register_payload,
            headers=self.headers,
        )
        assert response2.status_code == 409
        assert "already in use" in response2.json()["detail"].lower()

    def test_register_then_login_succeeds(self) -> None:
        """Test full flow: register then login."""
        email = f"user_{uuid.uuid4()}@example.com"
        password = "ValidPass@123"
        device_id = str(uuid.uuid4())

        # Register
        register_payload = {
            "email": email,
            "password": password,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        register_response = requests.post(
            f"{self.base_url}/user/auth/register",
            json=register_payload,
            headers=self.headers,
        )
        assert register_response.status_code == 200
        assert register_response.json()["status"] == "pending_verification"
        
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        otp = r.get(f"otp:{email}")

        verify_payload = {
            "email": email,
            "password": password,
            "otp": otp,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        verify_response = requests.post(
            f"{self.base_url}/user/auth/register/verify",
            json=verify_payload,
            headers=self.headers,
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["is_new_user"] is True
        register_token = verify_response.json()["access_token"]

        # Login with same credentials
        login_payload = {
            "email": email,
            "password": password,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        login_response = requests.post(
            f"{self.base_url}/user/auth/login",
            json=login_payload,
            headers=self.headers,
        )
        assert login_response.status_code == 200
        assert login_response.json()["is_new_user"] is False
        login_token = login_response.json()["access_token"]

        # Both tokens should work
        assert register_token
        assert login_token

    def test_login_with_wrong_password_fails(self) -> None:
        """Test that login with wrong password returns 401."""
        email = f"user_{uuid.uuid4()}@example.com"
        password = "CorrectPass@123"
        device_id = str(uuid.uuid4())

        # Register first
        register_payload = {
            "email": email,
            "password": password,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        register_response = requests.post(
            f"{self.base_url}/user/auth/register",
            json=register_payload,
            headers=self.headers,
        )
        assert register_response.status_code == 200
        
        import redis
        r = redis.Redis(host="localhost", port=6379, decode_responses=True)
        otp = r.get(f"otp:{email}")

        verify_payload = {
            "email": email,
            "password": password,
            "otp": otp,
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        verify_response = requests.post(
            f"{self.base_url}/user/auth/register/verify",
            json=verify_payload,
            headers=self.headers,
        )
        assert verify_response.status_code == 200

        # Try to login with wrong password
        login_payload = {
            "email": email,
            "password": "WrongPass@123",
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": device_id,
        }
        response = requests.post(
            f"{self.base_url}/user/auth/login",
            json=login_payload,
            headers=self.headers,
        )
        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_register_requires_password(self) -> None:
        """Test that register requires a password."""
        payload = {
            "email": "user@example.com",
            "device_name": "TestDevice",
            "device_type": "android",
            "device_id": str(uuid.uuid4()),
            # Missing password
        }
        response = requests.post(
            f"{self.base_url}/user/auth/register",
            json=payload,
            headers=self.headers,
        )
        assert response.status_code == 422

    def test_login_requires_device_type(self) -> None:
        """Test that login requires device_type."""
        payload = {
            "email": "user@example.com",
            "password": "ValidPass@123",
            "device_name": "TestDevice",
            "device_id": str(uuid.uuid4()),
            # Missing device_type
        }
        response = requests.post(
            f"{self.base_url}/user/auth/login",
            json=payload,
            headers=self.headers,
        )
        assert response.status_code == 422
