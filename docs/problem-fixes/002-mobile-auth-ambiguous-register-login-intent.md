# 002 - Mobile Auth: Split Register/Login Endpoints

## Status

Implemented. The ambiguous `/user/auth/register-login` endpoint is replaced with explicit `/user/auth/register` and `/user/auth/login` endpoints.

## Problem

`POST /user/auth/register-login` combined registration and login without an explicit intent. When a client attempted to login with an unknown email, the service silently created an account instead of rejecting the login attempt.

### Scenario: Email Typo

1. User A exists with email `user@example.com`.
2. User A attempts to login but typos their email as `usera@example.com`.
3. The system does not find a user with `usera@example.com`.
4. Instead of failing the login, the system creates a new account for `usera@example.com`.
5. User A is now confused: they have two accounts, the login failed mysteriously, and they may think they lost access to their original account.

### Risky Behaviors

- **User enumeration via account creation**: An attacker can infer whether an email is registered by observing the response behavior.
- **Accidental duplicate accounts**: Typos in login lead to new account creation, fragmenting user data and confusing users.
- **No UX clarity**: Clients cannot distinguish between "registration succeeded, account created" and "login succeeded, existing account accessed."

## Root Cause

The endpoint contained both registration and login logic in a single route and automatically created users when `get_user_by_email` returned `None`. Without explicit endpoints, there was no strict boundary between the two flows.

## Fix Location

- `app/schema/request/mobile/auth.py`: introduce `MobileRegisterRequest` and `MobileLoginRequest` (shared base validation).
- `app/service/users.py`: split logic into `AuthService.mobile_register()` and `AuthService.mobile_login()`.
- `app/router/mobile/auth.py`: replace `/user/auth/register-login` with `/user/auth/register` and `/user/auth/login`.
- Tests:
  - `tests/unit/test_mobile_auth_request_validation.py`
  - `tests/unit/test_mobile_auth_intent_validation.py`
  - `tests/e2e/test_mobile_auth_intent_e2e.py`

## Fix Behavior

After the fix:

- `POST /user/auth/login` with unknown email returns `401 Unauthorized` ("User not found; consider registering instead").
- `POST /user/auth/register` with existing email returns `409 Conflict` ("Email already in use; please login instead").
- `POST /user/auth/login` with correct credentials succeeds.
- `POST /user/auth/register` with a new email succeeds (`is_new_user = True`).

## Test Showcase

Example endpoint tests (in `tests/unit/test_mobile_auth_request_validation.py`):

```python
@pytest.mark.parametrize("field", ["password", "device_name", "device_type"])
@pytest.mark.parametrize("value", ["", "   "])
def test_register_login_rejects_empty_required_text_fields(
    client: TestClient,
    fake_container: FakeContainer,
    field: str,
    value: str,
) -> None:
    for endpoint in ("/user/auth/register", "/user/auth/login"):
        payload = _valid_payload()
        payload[field] = value

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
```

Example service tests (in `tests/unit/test_mobile_auth_intent_validation.py`):

```python
def test_login_with_unknown_email_is_rejected() -> None:
    req = MobileLoginRequest(
        email="unknown@example.com",
        password="validpass123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )
    with pytest.raises(HTTPException):
        asyncio.run(service.mobile_login(FakeRedis(), req))

def test_register_with_existing_email_is_rejected() -> None:
    req = MobileRegisterRequest(
        email="user@example.com",
        password="validpass123",
        device_name="Pixel 8",
        device_type="android",
        device_id=uuid.uuid4(),
    )
    with pytest.raises(HTTPException):
        asyncio.run(service.mobile_register(FakeRedis(), req))
```

Example e2e test (in `tests/e2e/test_mobile_auth_intent_e2e.py`):

```python
@pytest.mark.skipif(not os.getenv("MULTAI_RUN_E2E"), reason="E2E disabled")
def test_register_then_login_succeeds_e2e() -> None:
    base_url = os.getenv("MULTAI_E2E_BASE_URL", "http://localhost:8000")
    email = f"user_{uuid.uuid4()}@example.com"
    password = "validpass123"
    device_id = str(uuid.uuid4())

    register_payload = {
        "email": email,
        "password": password,
        "device_name": "TestDevice",
        "device_type": "android",
        "device_id": device_id,
    }
    register_response = requests.post(f"{base_url}/user/auth/register", json=register_payload)
    assert register_response.status_code == 200

    login_payload = {
        "email": email,
        "password": password,
        "device_name": "TestDevice",
        "device_type": "android",
        "device_id": device_id,
    }
    login_response = requests.post(f"{base_url}/user/auth/login", json=login_payload)
    assert login_response.status_code == 200
```
