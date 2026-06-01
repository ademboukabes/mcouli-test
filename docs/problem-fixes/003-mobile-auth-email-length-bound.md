# 003 - Mobile Auth Email Length Bound

## Status

Fixed. Mobile auth emails are now bounded at the API request boundary before they can reach the database.

## Problem

`EmailStr` validates email syntax, but it does not by itself guarantee that the accepted value fits the `users.email` database column. A payload with a syntactically valid email longer than 255 characters could pass request validation and then fail later when inserted or queried against the database.

That creates avoidable late failures and makes the API response depend on database behavior instead of the request contract.

## Root Cause

The mobile auth request schema previously relied on `EmailStr` alone for the `email` field. The database column is constrained to 255 characters, so the schema needed to mirror that limit.

## Fix Location

- `app/schema/request/mobile/auth.py`: `MobileAuthBaseRequest.email` is declared as `EmailStr = Field(..., max_length=255)`.
- `app/schema/request/mobile/auth.py`: `_normalize_email()` trims and lowercases string input before `EmailStr` validation.

## Fix Behavior

After the fix:

- oversized email strings are rejected with `422 Unprocessable Entity`;
- normalized email values are what reach the auth service;
- database insert/update code no longer has to be the first layer that discovers overlong mobile-auth emails.

## Tests

Covered by `tests/unit/test_mobile_auth_request_validation.py`:

- `test_register_login_rejects_oversized_email()` posts an email longer than 255 characters to both `/user/auth/register` and `/user/auth/login`.
- The expected result is `422`.
- The fake auth service is not called, proving rejection happens at request validation time.
