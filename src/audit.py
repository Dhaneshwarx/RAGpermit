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