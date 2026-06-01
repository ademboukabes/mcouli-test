# 004 - Mobile Auth Concurrent Signup Race

## Status

Fixed. Duplicate-user races during registration are caught and converted to a conflict response.

## Problem

`AuthService.mobile_register()` first checks whether an email exists, then creates a user if no row is found. Two simultaneous requests for the same email can both pass the existence check before either insert commits.

Without handling the database uniqueness failure, the losing request can bubble up an `IntegrityError` as a generic server error instead of returning a clear duplicate-email response.

## Root Cause

The service relied on the pre-insert lookup as if it were enough to guarantee uniqueness. The real source of truth is the database unique constraint, so the registration path also needed to handle insert-time uniqueness errors.

## Fix Location

- `app/service/users.py`: `AuthService.mobile_register()` wraps `user_querier.create_user(...)` in a `try` block.
- `app/service/users.py`: `except SQLAlchemyError as exc` passes the database error to `DBException.handle(exc)`.
- `app/core/exceptions.py`: duplicate-key handling maps unique-constraint violations to a conflict response.

## Fix Behavior

After the fix:

- normal first registration succeeds;
- pre-existing email registration returns `409 Conflict`;
- race-condition duplicate insert errors are also returned as `409 Conflict` instead of `500 Internal Server Error`.

## Tests

Covered by `tests/unit/test_mobile_auth_intent_validation.py`:

- `test_register_concurrent_signup_integrity_error()` stubs `create_user()` to raise a SQLAlchemy `IntegrityError` with duplicate-key metadata.
- The test asserts that `mobile_register()` raises `HTTPException` with status `409`.
- The detail includes language indicating the email is already in use.
