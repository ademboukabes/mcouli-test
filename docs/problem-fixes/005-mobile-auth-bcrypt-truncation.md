# 005 - Mobile Auth Bcrypt 72-Byte Truncation

## Status

Fixed. Password hashing now avoids bcrypt's 72-byte input truncation by pre-hashing passwords before passing them to bcrypt.

## Problem

Bcrypt only uses the first 72 bytes of its password input. If the application passes raw user passwords directly to bcrypt, two long passwords that share the same first 72 bytes can verify against the same hash.

That is especially risky for long passphrases or generated passwords, where differences after byte 72 should still matter.

## Root Cause

The password hashing layer needed a stable input format whose length is safely below bcrypt's truncation boundary while still representing the full original password.

## Fix Location

- `app/core/securite.py`: `hash_password()` hashes the UTF-8 password with SHA-256, base64-encodes the digest, then passes that fixed-size value to bcrypt.
- `app/core/securite.py`: `verify_password()` applies the same SHA-256/base64 transform before bcrypt verification.

## Fix Behavior

After the fix:

- every byte of the original password contributes to the SHA-256 digest;
- bcrypt receives a fixed-length pre-hashed value, so its 72-byte truncation does not discard user-password suffixes;
- two long passwords with the same 72-byte prefix no longer verify against each other's hashes.

## Tests

Covered by `tests/unit/test_bcrypt_truncation.py`:

- `test_bcrypt_72_byte_truncation_is_prevented()` builds two passwords with an identical 72-byte prefix and different suffixes.
- Each password verifies with its own hash.
- Neither password verifies against the other password's hash.

## Note

This fix does not reject passwords over 72 bytes. It preserves support for long passwords by pre-hashing them safely before bcrypt.
