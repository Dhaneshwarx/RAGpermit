import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE = Path("logs/audit.jsonl")


def write_audit_entry(entry):
    # One JSON object per line. json.dumps escapes newlines and quotes,
    # so a hostile question cannot forge extra log lines.
    record = {"time": datetime.now(timezone.utc).isoformat(), **entry}
    line = json.dumps(record)

    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_FILE, "a", encoding="utf-8") as file:
        file.write(line + "\n")


def log_auth_failure(reason):
    # A failed sign-in. Only the status and a short reason code are recorded: never the token,
    # never a name taken from it, and never the question (policy section 6).
    write_audit_entry({"status": "auth_failed", "reason": reason})
