"""Administrator permissions are separate from document-reading roles."""

import json

from src.authorization import load_users
from src.config import workspace_path


def is_admin(user_id):
    if not isinstance(user_id, str) or not user_id:
        return False

    try:
        path = workspace_path("data/admins.json")
        with path.open("rb") as file:
            raw = file.read(4097)

        if len(raw) > 4096:
            return False

        administrators = json.loads(raw)
        if not isinstance(administrators, list):
            return False
        if not all(
            isinstance(name, str) and name.strip()
            for name in administrators
        ):
            return False

        users, rejected = load_users()
        return (
            not rejected
            and user_id in users
            and user_id in administrators
        )
    except (OSError, ValueError, TypeError, RecursionError):
        return False
