# 006 - Mobile Auth Password Complexity Policy

## Status

Fixed. Registration enforces a password complexity policy while login remains permissive enough to verify existing credentials.

## Problem

The mobile registration flow only had length validation. A user could register with a password that met the minimum length but lacked mixed case, digits, or special characters.

That created a weaker baseline for new accounts and made the validation policy unclear to clients.

## Root Cause

Password validation lived mostly in generic field constraints. The registration schema needed explicit semantic validation for password composition.

## Fix Location

- `app/schema/request/mobile/auth.py`: `MobileAuthBaseRequest.password` has config-backed min/max length limits.
- `app/schema/request/mobile/auth.py`: `MobileRegisterRequest._validate_password_complexity()` requires:
  - at least one uppercase letter;
  - at least one lowercase letter;
  - at least one digit;
  - at least one special character.
- `app/schema/request/mobile/auth.py`: `MobileLoginRequest` intentionally inherits only the shared base validation and does not enforce registration complexity on login attempts.

## Fix Behavior

After the fix:

- weak new-registration passwords fail with `422`;
- valid complex registration passwords pass;
- login still accepts syntactically valid password strings even if they do not meet the current registration complexity policy, so older credentials can still be checked by `verify_password()`.

## Tests

Covered by `tests/unit/test_mobile_auth_request_validation.py`:

- `test_register_enforces_password_complexity()` verifies valid complex passwords pass and missing uppercase/lowercase/digit/special-character cases fail.
- `test_login_does_not_enforce_password_complexity()` verifies login can still attempt verification with a password that lacks the registration-only complexity requirement.

The live e2e fixtures in `tests/e2e/test_mobile_auth_intent_e2e.py` and `tests/e2e/test_mobile_auth_request_validation_e2e.py` use complex passwords such as `ValidPass@123` so registration tests exercise the current policy.
