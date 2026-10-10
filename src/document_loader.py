from src.policy_values import DOCUMENT_DEPARTMENTS, VALID_CLEARANCES, VALID_ROLES

EXPECTED_HEADER_KEYS = {"doc_id", "title", "department", "clearance", "allowed_roles"}


def split_header_and_body(text):
    lines = text.split("\n")

    # The header must start on line 1. Anything else means no valid header.
    if lines[0].strip() != "---":
        raise ValueError("document must start with a --- line")

    # Find the first closing --- line after the opening one.
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            header_text = "\n".join(lines[1:index])
            body_text = "\n".join(lines[index + 1:])
            return header_text, body_text

    raise ValueError("header is never closed with a second --- line")


def parse_header_lines(header_text):
    fields = {}

    for line in header_text.split("\n"):
        if line.strip() == "":
            continue

        # Split at the first colon only, so a title may contain colons.
        if ":" not in line:
            raise ValueError("header line has no colon: " + repr(line))
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key not in EXPECTED_HEADER_KEYS:
            raise ValueError("unknown header field: " + repr(key))
        if key in fields:
            raise ValueError("header field appears twice: " + repr(key))

        fields[key] = value

    missing = EXPECTED_HEADER_KEYS - set(fields)
    if missing:
        raise ValueError("header is missing: " + ", ".join(sorted(missing)))

    return fields


def parse_clearance(text):
    # Compare as text, so "02", "+2" or "2.0" are never quietly accepted as 2.
    for number in VALID_CLEARANCES:
        if text == str(number):
            return number
    raise ValueError("invalid clearance: " + repr(text))


def parse_allowed_roles(text):
    if not (text.startswith("[") and text.endswith("]")):
        raise ValueError("allowed_roles must be inside [ ]: " + repr(text))

    inside = text[1:-1].strip()
    if inside == "":
        return []  # an empty list means no extra roles

    roles = []
    for part in inside.split(","):
        role = part.strip()
        if role not in VALID_ROLES:
            raise ValueError("invalid role in allowed_roles: " + repr(role))
        roles.append(role)
    return roles


def validate_header(fields):
    if fields["doc_id"] == "":
        raise ValueError("doc_id is empty")
    if fields["title"] == "":
        raise ValueError("title is empty")
    if fields["department"] not in DOCUMENT_DEPARTMENTS:
        raise ValueError("invalid department: " + repr(fields["department"]))

    return {
        "doc_id": fields["doc_id"],
        "title": fields["title"],
        "department": fields["department"],
        "clearance": parse_clearance(fields["clearance"]),
        "allowed_roles": parse_allowed_roles(fields["allowed_roles"]),
    }





def load_document(path):
    text = path.read_text(encoding="utf-8")
    header_text, body_text = split_header_and_body(text)
    header = validate_header(parse_header_lines(header_text))

    if header["doc_id"] != path.stem:
        raise ValueError(
            "doc_id " + repr(header["doc_id"]) + " does not match file name " + repr(path.stem)
        )

    return {"header": header, "body": body_text}


def load_all_documents(folder):
    accepted = []
    rejected = []

    for path in sorted(folder.glob("*.md")):
        try:
            accepted.append(load_document(path))
        except ValueError as error:
            rejected.append((path.name, str(error)))

    return accepted, rejected

