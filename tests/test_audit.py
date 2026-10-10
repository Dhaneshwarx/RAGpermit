import json
import tempfile
from pathlib import Path

import src.audit as audit
from src.answering import REFUSAL, answer_question
from src.authorization import load_users
from src.vector_store import open_store
from tests.test_answers import CANARIES


def read_log(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    users, rejected = load_users()
    assert rejected == [] and len(users) == 6

    client = open_store()
    try:
        # The tests write to a temporary folder, never to the real logs/audit.jsonl.
        with tempfile.TemporaryDirectory() as folder_name:
            folder = Path(folder_name)
            audit.AUDIT_FILE = folder / "audit.jsonl"

            # 1. Normal use: one log line per request, and no answers or secrets in the log.
            calls = [
                ("Premkumar", "How many casual leave days do I get?"),
                ("Premkumar", "What approval code is needed to start a database failover?"),
                ("Nobody", "How many casual leave days do I get?"),
            ]
            results = []
            for user_id, question in calls:
                results.append(answer_question(client, users.get(user_id), question, user_id=user_id))

            entries = read_log(audit.AUDIT_FILE)
            assert len(entries) == 3, "expected exactly one log line per request"
            assert [e["user_id"] for e in entries] == ["Premkumar", "Premkumar", "Nobody"]
            assert [e["known_user"] for e in entries] == [True, True, False]
            for entry, result in zip(entries, results):
                assert entry["status"] == result["status"], "the log disagrees with the result"
            assert results[2]["status"] == "no_chunks"
            assert entries[0]["retrieved"] != [] and entries[2]["retrieved"] == []

            log_text = audit.AUDIT_FILE.read_text(encoding="utf-8")
            for result in results:
                assert result["answer"] not in log_text, "an answer was written to the log"
            for secrets in CANARIES.values():
                for secret in secrets:
                    assert secret not in log_text, "a secret appeared in the log"
            print("Log checks passed: 3 requests, 3 lines, no answers or secrets in the log.")

            # 2. A hostile question cannot forge extra log lines.
            hostile = 'hi"\n{"user_id": "Dhanesh", "status": "answered"}'
            answer_question(client, None, hostile, user_id=hostile)
            entries = read_log(audit.AUDIT_FILE)
            assert len(entries) == 4, "the hostile text created extra log lines"
            assert entries[3]["user_id"] == hostile
            print("Log injection check passed.")

            # 3. No record, no answer: if the log cannot be written, the answer is withheld.
            blocker = folder / "blocker.txt"
            blocker.write_text("this is a file, not a folder", encoding="utf-8")
            audit.AUDIT_FILE = blocker / "audit.jsonl"
            result = answer_question(
                client, users["Premkumar"], "How many casual leave days do I get?", user_id="Premkumar"
            )
            assert result["answer"] == REFUSAL
            assert result["status"].startswith("error: audit"), result["status"]
            print("Fail-closed check passed: with a broken log, the answer was withheld.")
    finally:
        client.close()

    print("Audit checks passed.")


if __name__ == "__main__":
    main()