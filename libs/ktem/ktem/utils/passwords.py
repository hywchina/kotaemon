"""Password hashing helpers with transparent legacy-hash migration."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

SCHEME = "pbkdf2_sha256"
DEFAULT_ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(
    password: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
    salt: bytes | None = None,
) -> str:
    """Hash a password using PBKDF2-SHA256 and a per-password random salt."""

    if not password:
        return ""
    actual_salt = salt or secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        actual_salt,
        iterations,
    )
    return f"{SCHEME}${iterations}${actual_salt.hex()}${digest.hex()}"


def _is_legacy_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def verify_password(password: str, encoded: str) -> bool:
    """Verify current PBKDF2 hashes and legacy unsalted SHA-256 hashes."""

    if not password or not encoded:
        return False

    if _is_legacy_sha256(encoded):
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, encoded)

    try:
        scheme, raw_iterations, raw_salt, raw_digest = encoded.split("$", 3)
        if scheme != SCHEME:
            return False
        iterations = int(raw_iterations)
        salt = bytes.fromhex(raw_salt)
        expected = bytes.fromhex(raw_digest)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def password_needs_upgrade(encoded: str) -> bool:
    """Return whether a stored hash should be replaced after successful login."""

    if _is_legacy_sha256(encoded):
        return True
    try:
        scheme, raw_iterations, _, _ = encoded.split("$", 3)
        return scheme != SCHEME or int(raw_iterations) < DEFAULT_ITERATIONS
    except (TypeError, ValueError):
        return True


def verify_and_upgrade(password: str, encoded: str) -> tuple[bool, str | None]:
    """Verify a password and return a stronger replacement hash when needed."""

    if not verify_password(password, encoded):
        return False, None
    if password_needs_upgrade(encoded):
        return True, hash_password(password)
    return True, None


def insecure_default_passwords() -> set[str]:
    """Return deployment passwords that must never be used as bootstrap secrets."""

    configured = os.getenv("KH_INSECURE_PASSWORDS", "admin,password,12345678")
    return {value.strip().lower() for value in configured.split(",") if value.strip()}
