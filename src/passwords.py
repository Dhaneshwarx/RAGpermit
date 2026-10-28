"""Password hashing helpers. No passwords are written to disk or logged."""

import hashlib
import hmac
import secrets

ITERATIONS = 600_000
MIN_PASSWORD_CHARS = 15
MAX_PASSWORD_CHARS = 128


def password_bytes(password):
    if not isinstance(password, str):
        raise ValueError("Password must be text.")
    if not MIN_PASSWORD_CHARS <= len(password) <= MAX_PASSWORD_CHARS:
        raise ValueError("Password must contain 15 to 128 characters.")
    # Preserve spaces and case exactly; never silently trim a password.
    return password.encode("utf-8")


def hash_password(password):
    raw = password_bytes(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", raw, salt, ITERATIONS, dklen=32
    )
    return {
        "algorithm": "pbkdf2-sha256",
        "iterations": ITERATIONS,
        "salt": salt.hex(),
        "hash": digest.hex(),
    }


def verify_password(password, record):
    try:
        raw = password_bytes(password)
        if not isinstance(record, dict):
            return False
        if set(record) != {"algorithm", "iterations", "salt", "hash"}:
            return False
        if record["algorithm"] != "pbkdf2-sha256":
            return False
        # Do not let stored data select an arbitrary computation cost.
        if type(record["iterations"]) is not int:
            return False
        if record["iterations"] != ITERATIONS:
            return False
        for field, length in (("salt", 32), ("hash", 64)):
            value = record[field]
            if not isinstance(value, str) or len(value) != length:
                return False
            if any(char not in "0123456789abcdef" for char in value):
                return False
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
        actual = hashlib.pbkdf2_hmac(
            "sha256", raw, salt, ITERATIONS, dklen=32
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False
