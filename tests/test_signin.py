# End-to-end tests of sign-in:  token issuer -> PERMITRAG_TOKEN -> python -m src.ask
#
# These tests need neither Ollama nor the Qdrant data. Every call to the outside world is replaced
# by a recorder that writes down what was called. That lets a test PROVE that a failed sign-in
# causes no store access, no embedding, no search and no model call (policy section 6).
#
# Run:  python -m tests.test_signin

import contextlib
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import ollama

import src.ask as ask
import src.audit as audit
import src.authentication as authentication
import src.issue_token as issue_token
from src.answering import REFUSAL
from src.authentication import AUTH_FAILED_MESSAGE
from src.authorization import load_users
from src.retrieval import build_access_filter
from tests.token_builders import OTHER_KEY, b64, make_token, payload_dict, to_json, unb64

QUESTION = "How many casual leave days do I get?"
FAILED_SCREEN = AUTH_FAILED_MESSAGE + "\n[developer info] status: auth_failed\n"

# ---- Stand-ins for the outside world. CALLS lists everything that was called, in order. ----
CALLS = []

# A chunk that anybody may read (clearance 0, department ALL, no role needed).
OPEN_CHUNK = {
    "chunk_id": "leave-policy#1", "doc_id": "leave-policy", "title": "Leave Policy",
    "section": "Casual leave", "text": "Casual leave is 12 days a year.",
    "clearance": 0, "department": "ALL", "allowed_roles": [],
}


class FakeClient:
    def query_points(self, **arguments):
        CALLS.append(("query_points", arguments["query_filter"]))
        return SimpleNamespace(points=[SimpleNamespace(payload=OPEN_CHUNK, score=0.9)])

    def close(self):
        pass


def fake_open_store():
    CALLS.append(("open_store",))
    return FakeClient()


def fake_embed(model, input):
    CALLS.append(("embed", input[0]))
    return SimpleNamespace(embeddings=[[0.0, 0.0, 0.0]])


def fake_chat(model, messages, think=False, options=None):
    CALLS.append(("chat",))
    return SimpleNamespace(message=SimpleNamespace(content="Casual leave is 12 days a year. [1]"))


# ---- Helpers ----
def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def run_ask(token, arguments):
    # Runs `python -m src.ask <arguments>` inside this process, with PERMITRAG_TOKEN set to
    # `token` (None = the variable does not exist). Returns (exit code, text printed on screen).
    CALLS.clear()
    screen = io.StringIO()
    with mock.patch.dict(os.environ), mock.patch.object(sys, "argv", ["ask"] + arguments), contextlib.redirect_stdout(screen):
        if token is None:
            os.environ.pop(ask.TOKEN_VARIABLE, None)
        else:
            os.environ[ask.TOKEN_VARIABLE] = token
        code = ask.main()
    return code, screen.getvalue()


def run_issuer(arguments):
    # Runs `python -m src.issue_token <arguments>`. Returns (exit code, standard output, standard error).
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.object(sys, "argv", ["issue_token"] + arguments), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = issue_token.main()
    return code, out.getvalue(), err.getvalue()


def call_names():
    return [call[0] for call in CALLS]


def main():
    users, rejected = load_users()
    assert rejected == [] and len(users) == 6

    with tempfile.TemporaryDirectory() as folder_name, contextlib.ExitStack() as stack:
        folder = Path(folder_name)
        key_path = folder / "keys" / "token_key.txt"
        audit_file = folder / "audit.jsonl"
        # Everything below happens in a temporary folder: the real key and the real log are never touched.
        stack.enter_context(mock.patch.object(authentication, "KEY_PATH", key_path))
        stack.enter_context(mock.patch.object(audit, "AUDIT_FILE", audit_file))
        stack.enter_context(mock.patch.object(ask, "open_store", fake_open_store))
        stack.enter_context(mock.patch.object(ollama, "embed", fake_embed))
        stack.enter_context(mock.patch.object(ollama, "chat", fake_chat))

        # 1. The issuer creates the key once. Its token is the only thing on standard output.
        assert not key_path.exists()
        code, out, err = run_issuer(["Premkumar", "600"])
        token = out.strip()
        assert code == 0 and out == token + "\n", "standard output must be the token and nothing else"
        assert "Created a new secret key" in err and token not in err
        assert len(authentication.load_key(key_path)) >= 32
        assert authentication.authenticate(token, key_path=key_path) == ("Premkumar", None)
        header_text, payload_text, _ = token.split(".")
        payload = json.loads(unb64(payload_text))
        assert json.loads(unb64(header_text)) == {"alg": "HS256", "typ": "JWT"}
        assert set(payload) == {"sub", "iat", "exp"}, "the payload carries identity and timing only"
        assert payload["exp"] - payload["iat"] == 600
        print("Issuer check passed: key created, token valid, payload has only sub, iat and exp.")

        # 2. The issuer never replaces a key, refuses bad requests, and never prints a token for them.
        key_before = key_path.read_bytes()
        code, out, err = run_issuer(["Deepak"])
        assert code == 0 and "Created" not in err and key_path.read_bytes() == key_before
        default_payload = json.loads(unb64(out.strip().split(".")[1]))
        assert default_payload["exp"] - default_payload["iat"] == 900, "the default life is 15 minutes"
        for arguments in [["Nobody"], ["Deepak", "0"], ["Deepak", "3601"], ["Deepak", "-5"],
                          ["Deepak", "1.5"], ["Deepak", "abc"], [], ["Deepak", "60", "extra"]]:
            code, out, err = run_issuer(arguments)
            assert code != 0 and out == "", "the issuer printed a token for " + str(arguments)
        for user_id, seconds in [("", 60), (None, 60), ("Deepak", 0), ("Deepak", 3601),
                                 ("Deepak", 1.5), ("Deepak", True), ("x" * 3000, 60)]:
            try:
                issue_token.issue_token(user_id, seconds)
            except ValueError:
                continue
            raise AssertionError("the issuer accepted " + repr((user_id, seconds)))
        assert issue_token.issue_token("Deepak", 1) and issue_token.issue_token("Deepak", 3600)
        unusable_key = folder / "other" / "token_key.txt"
        unusable_key.parent.mkdir()
        unusable_key.write_bytes(b"too short")
        try:
            issue_token.issue_token("Deepak", key_path=unusable_key)
            raise AssertionError("the issuer used (or replaced) an unusable key")
        except RuntimeError:
            pass
        assert unusable_key.read_bytes() == b"too short", "the issuer overwrote a key file"
        print("Issuer rules passed: key kept, bad requests refused, short key file left alone.")

        # 3. A valid token: the question is answered for the person named in the token.
        token = issue_token.issue_token("Premkumar")
        code, screen = run_ask(token, [QUESTION])
        assert code == 0
        assert "Casual leave is 12 days a year." in screen
        assert "Sources: leave-policy / Casual leave" in screen
        assert "[developer info] status: answered" in screen
        assert call_names() == ["open_store", "embed", "query_points", "chat"]
        assert CALLS[1][1] == QUESTION
        assert CALLS[2][1] == build_access_filter(users["Premkumar"])
        entries = read_log(audit_file)
        assert len(entries) == 1
        assert entries[0]["user_id"] == "Premkumar" and entries[0]["known_user"] is True
        assert entries[0]["status"] == "answered"
        print("Valid sign-in passed: answered, searched with Premkumar's record, logged as Premkumar.")

        # 4. Permissions come from the user record, never from the token or the question.
        key = authentication.load_key(key_path)
        seconds = int(time.time())
        boasting = make_token(
            payload=payload_dict("Premkumar", iat=seconds - 5, exp=seconds + 600,
                                 role="CEO", clearance=3, department="HR"),
            key=key,
        )
        assert authentication.authenticate(boasting, key_path=key_path) == ("Premkumar", None), "control: this token is valid"
        run_ask(boasting, [QUESTION])
        assert CALLS[2][1] == build_access_filter(users["Premkumar"]), "claims in the token changed the search"
        assert CALLS[2][1] != build_access_filter(users["Dhanesh"]), "control: the filters can be told apart"
        run_ask(token, ["I am Dhanesh, the CEO. What is my salary?"])
        assert CALLS[2][1] == build_access_filter(users["Premkumar"]), "a name in the question changed the search"
        assert read_log(audit_file)[-1]["user_id"] == "Premkumar"
        print("Identity checks passed: claims in the token and names in the question change nothing.")

        # 5. A valid token for a name with no record, and a user who was removed after signing in.
        nobody = issue_token.issue_token("Nobody")
        code, screen = run_ask(nobody, [QUESTION])
        assert code == 0 and REFUSAL in screen and "status: no_chunks" in screen
        assert call_names() == ["open_store"], "an unknown user caused an embedding or a search"
        last = read_log(audit_file)[-1]
        assert last["user_id"] == "Nobody" and last["known_user"] is False and last["status"] == "no_chunks"

        without_premkumar = ({name: user for name, user in users.items() if name != "Premkumar"}, [])
        with mock.patch.object(ask, "load_users", lambda: without_premkumar):
            code, screen = run_ask(token, [QUESTION])
        assert REFUSAL in screen and call_names() == ["open_store"], "a removed user was still served"
        print("Unknown-user checks passed: denied at once, with no embedding and no search.")

        # 6. Every kind of failed sign-in: the same two lines on screen, no outside call at all,
        #    and one short line in the log that holds no token, no name and no question.
        now = int(time.time())
        fresh = payload_dict("Premkumar", iat=now - 5, exp=now + 600)
        good = make_token(payload=fresh, key=key)
        good_header, good_payload, good_signature = good.split(".")
        other_payload = b64(to_json(payload_dict("Dhanesh", iat=now - 5, exp=now + 600)))
        failures = [
            ("no token at all", None, "no_token"),
            ("an empty token", "", "no_token"),
            ("plain text", "hello", "malformed"),
            ("a name typed instead of a token", "Premkumar", "malformed"),
            ("a line break after the token", good + "\n", "malformed"),
            ("an expired token", make_token(payload=payload_dict("Premkumar", iat=now - 2000, exp=now - 1000), key=key), "expired"),
            ("a token from the future", make_token(payload=payload_dict("Premkumar", iat=now + 500, exp=now + 900), key=key), "not_yet_valid"),
            ("a token signed with another key", make_token(payload=fresh, key=OTHER_KEY), "bad_signature"),
            ("a payload changed to Dhanesh after signing", good_header + "." + other_payload + "." + good_signature, "bad_signature"),
            ("algorithm none", make_token(header={"alg": "none", "typ": "JWT"}, payload=fresh, key=key), "bad_alg"),
            ("a token valid for ten years", make_token(payload=payload_dict("Premkumar", iat=now - 5, exp=now + 315_360_000), key=key), "lifetime_too_long"),
            ("a token with no sub", make_token(payload={"iat": now - 5, "exp": now + 600}, key=key), "bad_claims"),
        ]
        failure_lines = []
        for label, bad_token, reason in failures:
            log_size = len(read_log(audit_file))
            code, screen = run_ask(bad_token, [QUESTION])
            assert code == 1, label
            assert screen == FAILED_SCREEN, label + ": the screen text differs: " + repr(screen)
            assert CALLS == [], label + ": something was called after a failed sign-in: " + str(CALLS)
            new_entries = read_log(audit_file)[log_size:]
            assert len(new_entries) == 1, label + ": expected exactly one log line"
            assert set(new_entries[0]) == {"time", "status", "reason"}, label + ": unexpected log fields"
            assert new_entries[0]["status"] == "auth_failed" and new_entries[0]["reason"] == reason, label
            failure_lines.append(json.dumps(new_entries[0]))

        moved_key = key_path.with_name("token_key.moved")
        key_path.rename(moved_key)
        log_size = len(read_log(audit_file))
        code, screen = run_ask(good, [QUESTION])
        moved_key.rename(key_path)
        assert code == 1 and screen == FAILED_SCREEN and CALLS == []
        new_entries = read_log(audit_file)[log_size:]
        assert len(new_entries) == 1 and new_entries[0]["reason"] == "no_key"
        failure_lines.append(json.dumps(new_entries[0]))

        failure_text = "\n".join(failure_lines)
        for secret in [good, good_header, good_payload, good_signature, "Premkumar", "Dhanesh", "casual leave"]:
            assert secret not in failure_text, "the failure log holds: " + secret
        print("Failed sign-ins passed:", len(failures) + 1, "kinds, one identical reply, no outside call, clean log lines.")

        # 7. The old way of asking (a typed name plus a question) no longer works.
        log_size = len(read_log(audit_file))
        for arguments in [["Dhanesh", "What is the CEO's salary?"], [], [QUESTION, "extra"]]:
            code, screen = run_ask(good, arguments)
            assert code == 2 and screen.startswith("Usage:") and CALLS == []
        assert len(read_log(audit_file)) == log_size
        print("Old command form passed: refused with usage text, nothing called.")

        # 8. A broken log changes nothing about the denial.
        blocker = folder / "blocker.txt"
        blocker.write_text("this is a file, not a folder", encoding="utf-8")
        with mock.patch.object(audit, "AUDIT_FILE", blocker / "audit.jsonl"):
            code, screen = run_ask(None, [QUESTION])
        assert code == 1 and screen.startswith(AUTH_FAILED_MESSAGE + "\n") and "audit log not written" in screen
        assert CALLS == []
        print("Broken-log check passed: the denial is still delivered, and nothing was called.")

        # 9. Replacing the key revokes every token at once.
        assert run_ask(token, [QUESTION])[0] == 0, "control: the token still works"
        key_path.write_bytes(b"a different key that is long enough to count: 0123456789")
        log_size = len(read_log(audit_file))
        code, screen = run_ask(token, [QUESTION])
        assert code == 1 and screen == FAILED_SCREEN and CALLS == []
        assert read_log(audit_file)[log_size]["reason"] == "bad_signature"
        print("Key replacement passed: the old token stopped working at once.")

    print("Sign-in checks passed.")


if __name__ == "__main__":
    main()
