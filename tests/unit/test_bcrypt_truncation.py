from app.core.securite import hash_password, verify_password


def test_bcrypt_72_byte_truncation_is_prevented() -> None:
    # Create two passwords that are longer than 72 bytes and share the same 72-byte prefix
    prefix = "a" * 72
    pass1 = prefix + "X"
    pass2 = prefix + "Y"

    # Hash both passwords
    hash1 = hash_password(pass1)
    hash2 = hash_password(pass2)

    # They must produce different hashes (or at least pass2 must not verify with hash1)
    assert not verify_password(pass2, hash1)
    assert not verify_password(pass1, hash2)

    # Each must verify with its own hash
    assert verify_password(pass1, hash1)
    assert verify_password(pass2, hash2)
