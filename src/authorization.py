import json
from pathlib import Path

from src.policy_values import (
    DOCUMENT_DEPARTMENTS,
    USER_DEPARTMENTS,
    VALID_CLEARANCES,
    VALID_ROLES,
)

USERS_FILE = Path("data/users.json")


def validate_user(record):
    for key in ("user_id", "department", "role", "clearance"):
        if key not in record:
            raise ValueError("user record is missing " + key)

    # "type(...) is int" is stricter than isinstance: in Python, True counts as 1,
    # and a JSON true must never be accepted as clearance 1.
    if type(record["clearance"]) is not int or record["clearance"] not in VALID_CLEARANCES:
        raise ValueError("invalid clearance: " + repr(record["clearance"]))
    if record["department"] not in USER_DEPARTMENTS:
        raise ValueError("invalid department: " + repr(record["department"]))
    if record["role"] not in VALID_ROLES:
        raise ValueError("invalid role: " + repr(record["role"]))
    if not isinstance(record["user_id"], str) or record["user_id"] == "":
        raise ValueError("invalid user_id: " + repr(record["user_id"]))

    return {
        "user_id": record["user_id"],
        "department": record["department"],
        "role": record["role"],
        "clearance": record["clearance"],
    }


def load_users(path=USERS_FILE):
    users = {}
    rejected = []

    for record in json.loads(path.read_text(encoding="utf-8")):
        try:
            user = validate_user(record)
        except ValueError as error:
            rejected.append(str(error))
            continue

        # Two records with one user_id would be ambiguous: stop instead of guessing.
        if user["user_id"] in users:
            raise ValueError("duplicate user_id: " + repr(user["user_id"]))
        users[user["user_id"]] = user

    return users, rejected


def has_valid_access_fields(doc):
    clearance = doc.get("clearance")
    allowed_roles = doc.get("allowed_roles")
    return (
        type(clearance) is int
        and clearance in VALID_CLEARANCES
        and doc.get("department") in DOCUMENT_DEPARTMENTS
        and isinstance(allowed_roles, list)
        and all(role in VALID_ROLES for role in allowed_roles)
    )


def can_read(user, doc):
    # The one place that decides access. Anything unknown or invalid returns False;
    # the only way to get True is to pass every check with valid data.
    if user is None or not has_valid_access_fields(doc):
        return False
    if doc["clearance"] > user["clearance"]:
        return False

    return (
        doc["department"] == "ALL"
        or doc["department"] == user["department"]
        or user["role"] in doc["allowed_roles"]
    )