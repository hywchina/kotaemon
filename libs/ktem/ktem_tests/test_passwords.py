import hashlib

from ktem.utils.passwords import (
    DEFAULT_ITERATIONS,
    hash_password,
    password_needs_upgrade,
    verify_and_upgrade,
    verify_password,
)


def test_password_hash_uses_salt_and_verifies() -> None:
    first = hash_password("Hospital-Password-1")
    second = hash_password("Hospital-Password-1")

    assert first != second
    assert verify_password("Hospital-Password-1", first)
    assert not verify_password("wrong", first)


def test_legacy_sha256_hash_is_upgraded_after_login() -> None:
    legacy = hashlib.sha256(b"Hospital-Password-1").hexdigest()

    valid, replacement = verify_and_upgrade("Hospital-Password-1", legacy)

    assert valid
    assert replacement
    assert replacement.startswith(f"pbkdf2_sha256${DEFAULT_ITERATIONS}$")
    assert verify_password("Hospital-Password-1", replacement)


def test_malformed_hash_fails_closed() -> None:
    assert not verify_password("password", "pbkdf2_sha256$bad$value")
    assert password_needs_upgrade("unknown$value")
