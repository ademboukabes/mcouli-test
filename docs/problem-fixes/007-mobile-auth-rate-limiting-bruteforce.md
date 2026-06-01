# 007 - Mobile Auth Rate Limiting And Brute-Force Protection

## Status

Fixed. Mobile login and registration now apply Redis-backed rate limits by email and client IP, and the test doubles have the required Redis methods.

## Problem

Mobile auth endpoints did not have brute-force protection. Attackers could repeatedly try passwords or enumerate registration/login behavior without a request counter at the service boundary.

An initial implementation added rate limiting, but tests failed because fake Redis/test doubles did not implement the new `incr()` and `expire()` methods, and live e2e tests shared one client IP bucket.

## Root Cause

The auth service needed a small atomic counter abstraction from Redis and tests needed to evolve with that new contract. The router also needed to pass a stable client identity into the service so IP-based throttling could work.

## Fix Location

- `app/core/config.py`: adds `RATE_LIMIT_LOGIN_MAX_ATTEMPTS`, `RATE_LIMIT_LOGIN_WINDOW_SECONDS`, and `TRUST_PROXY_HEADERS`.
- `app/infra/redis.py`: `RedisClient.incr()` and `RedisClient.expire()` expose the Redis operations needed by rate limiting.
- `app/router/mobile/auth.py`: `_get_client_ip()` derives client identity from `X-Forwarded-For`, `X-Real-IP`, or the socket client, depending on `TRUST_PROXY_HEADERS`.
- `app/router/mobile/auth.py`: `mobile_register()` and `mobile_login()` pass `client_ip` to the auth service.
- `app/service/users.py`: `AuthService.mobile_register()` and `AuthService.mobile_login()` check `rate:ip:{client_ip}` and `rate:email:{email}` before credential or signup work.
- `app/service/users.py`: `AuthService.check_rate_limit()` increments the Redis counter, sets the expiry on first use, and raises `429 Too Many Requests` after the configured limit.

## Fix Behavior

After the fix:

- repeated attempts from the same email are throttled;
- repeated attempts from the same client IP are throttled when a client IP is available;
- counters expire after the configured window;
- `429` responses include the service-level too-many-requests error path;
- live e2e tests isolate client IP buckets with `X-Forwarded-For` so one test does not accidentally consume another test's limit.

## Tests

Covered by:

- `tests/unit/test_mobile_auth_rate_limiting.py`: `test_rate_limiting_triggered_after_max_attempts()` verifies the first five login attempts pass and the sixth returns `429`.
- `tests/unit/test_mobile_auth_request_validation.py`: `test_mobile_auth_uses_forwarded_ip_for_rate_limit_identity()` verifies the router forwards the first `X-Forwarded-For` address into the auth service.
- `tests/e2e/test_mobile_auth_intent_e2e.py`: live e2e requests include a per-test `X-Forwarded-For` header, preventing shared-IP rate-limit collisions while still exercising real HTTP requests.
