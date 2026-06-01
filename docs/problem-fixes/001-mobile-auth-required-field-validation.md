# 001 - Mobile Auth Accepted Empty Or Unnormalized Input Fields

## Status

Fixed in `app/schema/request/mobile/auth.py` and covered by endpoint and e2e tests.

## Problem

`POST /user/auth/register` and `POST /user/auth/login` accepted weak request payloads because the shared mobile auth request model used plain `str` fields for `password`, `device_name`, and `device_type`.

The risky payloads were:

- empty password: `""`
- whitespace-only password: `"   "`
- empty or whitespace-only device name
- empty or whitespace-only device type
- device names and types with accidental surrounding whitespace
- mixed-case device types that would fragment downstream analytics
- oversized password/device strings because no upper bound existed

This created both correctness and data-quality problems. A mobile account could be registered with an empty password, and device records could be created with blank or inconsistent device metadata.

## Root Cause

The request model did not put validation at the boundary where the API payload enters the system.

Before the fix, the schema shape was effectively:

```python
class MobileAuthBaseRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str
    device_type: str
    device_id: UUID
```

Plain `str` accepts `""`, `"   "`, and arbitrarily large values. Since `app/service/users.py` trusts `MobileRegisterRequest` and `MobileLoginRequest`, bad values could flow directly into password hashing, user creation, and device creation.

## Fix Location

The fix is in [app/schema/request/mobile/auth.py](../../app/schema/request/mobile/auth.py).

- `app/schema/request/mobile/auth.py:8-22` adds `Field(...)` constraints:
  - password min/max length
  - device name min/max length
  - device type min/max length

- `app/schema/request/mobile/auth.py:25-30` normalizes email input:
  - trims surrounding whitespace
  - lowercases casing before `EmailStr` validation

- `app/schema/request/mobile/auth.py:32-44` validates required text fields:
  - rejects empty or whitespace-only values
  - trims password before length validation
  - trims `device_name`
  - trims and lowercases `device_type`

The config-backed limits are in [app/core/config.py](../../app/core/config.py):

- `app/core/config.py:39-43`
  - `MOBILE_AUTH_PASSWORD_MIN_LEN = 8`
  - `MOBILE_AUTH_PASSWORD_MAX_LEN = 128`
  - `MOBILE_AUTH_DEVICE_NAME_MAX_LEN = 64`
  - `MOBILE_AUTH_DEVICE_TYPE_MAX_LEN = 32`

The executable regression tests are in [tests/unit/test_mobile_auth_request_validation.py](../../tests/unit/test_mobile_auth_request_validation.py). They use FastAPI `TestClient` against the real `app.main.app` and the real `/user/auth/register-login` route.

The only dependency override is `get_container`, because FastAPI resolves that dependency before returning request-body validation errors. Without the override, the test tries to open a real Postgres connection before it can assert `422`.

- `tests/unit/test_mobile_auth_request_validation.py:50-56` creates a `TestClient` from the real app and overrides only the infrastructure container.
- `tests/unit/test_mobile_auth_request_validation.py:69-83` posts empty and whitespace-only values to the real endpoint and verifies the service is not called.
- `tests/unit/test_mobile_auth_request_validation.py:86-106` posts a valid payload and verifies the service receives normalized values.
- `tests/unit/test_mobile_auth_request_validation.py:109-119` posts a padded one-character password and verifies it is rejected before the service is called.

The live e2e tests are in [tests/e2e/test_mobile_auth_request_validation_e2e.py](../../tests/e2e/test_mobile_auth_request_validation_e2e.py):

- `tests/e2e/test_mobile_auth_request_validation_e2e.py:8-18` makes the test opt-in and points it at a real running backend.
- `tests/e2e/test_mobile_auth_request_validation_e2e.py:31-42` sends real HTTP requests for empty and whitespace-only fields.
- `tests/e2e/test_mobile_auth_request_validation_e2e.py:45-51` sends a real HTTP request for a padded short password.

## Fix Behavior

After the fix:

- `password=""` is rejected
- `password="   "` is rejected
- `device_name=""` and `device_name="   "` are rejected
- `device_type=""` and `device_type="   "` are rejected
- `" Pixel 8 "` becomes `"Pixel 8"`
- `" ANDROID "` becomes `"android"`
- `" USER@Example.COM "` becomes `"user@example.com"`
- `"       a"` is rejected because trimming happens before password length validation

## Test Showcase

These are the core endpoint tests that demonstrate the bug and the fix.

```python
@pytest.mark.parametrize("field", ["password", "device_name", "device_type"])
@pytest.mark.parametrize("value", ["", "   "])
def test_register_login_rejects_empty_required_text_fields(
    client,
    fake_container,
    field,
    value,
):
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        payload[field] = value

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
        assert getattr(fake_container.auth_service, attr) is None
```

Before the fix, those payloads were accepted by the endpoint because the fields were plain `str`. The second assertion makes the test real at the route boundary: invalid payloads must fail before they can reach `AuthService.mobile_register()` or `AuthService.mobile_login()`.

The request body is still written in the test because the test has to define the scenario. What makes this a real endpoint simulation is that the payload goes through FastAPI HTTP request handling, dependency solving, request-body parsing, Pydantic validation, and the actual route path instead of directly calling `MobileRegisterRequest(...)` or `MobileLoginRequest(...)`.

```python
def test_register_login_passes_normalized_input_to_service(client, fake_container):
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
```

Before the fix, device fields kept surrounding whitespace and mixed casing.

```python
def test_register_login_password_length_is_checked_after_trimming(
    client,
    fake_container,
):
    for endpoint, attr in (
        ("/user/auth/register", "register_request"),
        ("/user/auth/login", "login_request"),
    ):
        payload = _valid_payload()
        payload["password"] = "       a"

        response = client.post(endpoint, json=payload)

        assert response.status_code == 422
        assert getattr(fake_container.auth_service, attr) is None
```

This protects the password minimum-length rule from being bypassed by padding a one-character password with spaces.

## Verification

Endpoint test command:

```bash
.venv\Scripts\python.exe -m pytest tests\unit\test_mobile_auth_request_validation.py -q
```

Result:

```text
8 passed, 2 warnings in 4.07s
```

E2e skipped-mode command:

```bash
.venv\Scripts\python.exe -m pytest tests\e2e\test_mobile_auth_request_validation_e2e.py -q
```

Result:

```text
7 skipped in 0.16s
```

Live e2e command, after starting the backend and infrastructure:

```bash
$env:MULTAI_RUN_E2E = "1"
$env:MULTAI_E2E_BASE_URL = "http://localhost:8000"
.venv\Scripts\python.exe -m pytest tests\e2e\test_mobile_auth_request_validation_e2e.py -q
```

## Remaining Nearby Risks

This fix covers the empty-field and basic normalization problem. The workshop audit still lists separate follow-up issues:

- the combined register/login endpoint can still create a new account from an email typo
- plaintext email is still logged during auth attempts
- bcrypt still truncates passwords at 72 bytes unless the password policy prevents it
- `device_type` is normalized but still not restricted to an allowed enum
