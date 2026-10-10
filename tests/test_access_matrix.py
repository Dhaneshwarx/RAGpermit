import csv
from pathlib import Path

from src.authorization import can_read, load_users
from src.document_loader import load_all_documents

MATRIX_FILE = Path("tests/access_matrix.csv")
DOCS_FOLDER = Path("data/docs")


def read_matrix(path):
    # Returns {doc_id: {user_id: True or False}} from the answer key we worked out by hand.
    matrix = {}
    with open(path, encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            doc_id = row.pop("doc_id")
            matrix[doc_id] = {}
            for user_id, value in row.items():
                if value not in ("Y", "N"):
                    raise ValueError("matrix cell must be Y or N: " + doc_id + " / " + user_id + " = " + repr(value))
                matrix[doc_id][user_id] = (value == "Y")
    return matrix


def main():
    users, rejected_users = load_users()
    assert rejected_users == [], rejected_users
    assert len(users) == 6

    accepted, rejected_docs = load_all_documents(DOCS_FOLDER)
    assert rejected_docs == [], rejected_docs
    headers = {document["header"]["doc_id"]: document["header"] for document in accepted}

    matrix = read_matrix(MATRIX_FILE)
    assert set(matrix) == set(headers), "matrix and documents list different doc_ids"
    for row in matrix.values():
        assert set(row) == set(users), "matrix and users list different user_ids"

    mismatches = []
    allowed_count = 0
    for doc_id, header in headers.items():
        for user_id, user in users.items():
            expected = matrix[doc_id][user_id]
            actual = can_read(user, header)
            if actual:
                allowed_count += 1
            if actual != expected:
                mismatches.append((user_id, doc_id, "expected", expected, "got", actual))

    for mismatch in mismatches:
        print("MISMATCH:", mismatch)
    print(len(headers) * len(users), "pairs checked,", allowed_count, "allowed,", len(mismatches), "mismatches")
    assert mismatches == []

    # Deny by default (policy section 3): anything unknown or invalid is refused.
    some_user = list(users.values())[0]
    good = {"clearance": 0, "department": "ALL", "allowed_roles": []}
    assert can_read(some_user, good) is True  # control: this one must be allowed
    assert can_read(None, good) is False  # unknown user
    assert can_read(some_user, {"department": "ALL", "allowed_roles": []}) is False  # no clearance
    assert can_read(some_user, {**good, "clearance": True}) is False  # True must not count as 1
    assert can_read(some_user, {**good, "clearance": 7}) is False
    assert can_read(some_user, {**good, "department": "Enginering"}) is False
    assert can_read(some_user, {**good, "allowed_roles": ["Janitor"]}) is False
    assert can_read(some_user, {**good, "allowed_roles": "CEO"}) is False  # not a list
    print("Deny-by-default checks passed.")


if __name__ == "__main__":
    main()