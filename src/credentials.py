"""Local credential storage for trusted administrator setup."""

import hashlib
import json
import os
from pathlib import Path

from src.passwords import hash_password, verify_password

CREDENTIALS_DIR = Path(__file__).resolve().parent.parent / "keys" / "passwords"
MAX_RECORD_BYTES = 4096


def credential_path(user_id, directory=None):
    if not isinstance(user_id, str) or not 1 <= len(user_id) <= 256:
        raise ValueError("Invalid user ID.")
    # A digest filename prevents usernames from becoming filesystem paths.
    name = hashlib.sha256(user_id.encode("utf-8")).hexdigest() + ".json"
    folder = CREDENTIALS_DIR if directory is None else Path(directory)
    return folder / name


def create_credentials(user_id, password, directory=None):
    """Trusted setup operation; this is not public self-registration."""
    path = credential_path(user_id, directory)
    record = {"user_id": user_id, "password": hash_password(password)}
    data = json.dumps(record, ensure_ascii=True).encode("ascii")
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError("Credential record too large.")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: existing credentials are never overwritten.
    # Windows file access also depends on the folder's Windows permissions.
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "wb") as file:
        file.write(data)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate record field.")
        result[key] = value
    return result


def check_credentials(user_id, password, directory=None):
    """Missing, unreadable, malformed or mismatched records deny login."""
    try:
        path = credential_path(user_id, directory)
        with path.open("rb") as file:
            data = file.read(MAX_RECORD_BYTES + 1)
        if len(data) > MAX_RECORD_BYTES:
            return False
        record = json.loads(data, object_pairs_hook=unique_object)
        if not isinstance(record, dict):
            return False
        if set(record) != {"user_id", "password"}:
            return False
        if record["user_id"] != user_id:
            return False
        return verify_password(password, record["password"])
    except (OSError, ValueError, TypeError, RecursionError):
        return False
