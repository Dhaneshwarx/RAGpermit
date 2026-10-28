import contextlib
import getpass
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import src.audit as audit
import src.authentication as authentication
import src.credentials as credentials
import src.issue_token as issuer


class PasswordLoginTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.key = self.root / "token_key.txt"
        self.log = self.root / "audit.jsonl"
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(
            authentication, "KEY_PATH", self.key))
        self.stack.enter_context(mock.patch.object(
            credentials, "CREDENTIALS_DIR", self.root / "passwords"))
        self.stack.enter_context(mock.patch.object(
            audit, "AUDIT_FILE", self.log))
        self.stack.enter_context(mock.patch.object(
            issuer, "load_users", return_value=({"TestUser": {}}, [])))
        self.password = "Temporary login passphrase!"
        credentials.create_credentials("TestUser", self.password)

    def run_login(self, arguments, inputs):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(issuer.sys, "argv", ["issue_token"] + arguments):
            with mock.patch.object(issuer.getpass, "getpass",
                                   side_effect=inputs) as prompt:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = issuer.main()
        self.assertNotIn(self.password, out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue(), prompt.call_count

    def assert_denied(self, arguments, inputs):
        with mock.patch.object(issuer, "issue_token") as sign:
            code, out, err, _ = self.run_login(arguments, inputs)
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, authentication.AUTH_FAILED_MESSAGE + "\n")
        sign.assert_not_called()
        self.assertFalse(self.key.exists())

    def test_successful_login(self):
        code, out, err, calls = self.run_login(
            ["TestUser", "600"], [self.password])
        self.assertEqual(code, 0)
        self.assertEqual(calls, 1)
        token = out.strip()
        self.assertEqual(out, token + "\n")
        self.assertEqual(
            authentication.authenticate(token, key_path=self.key),
            ("TestUser", None))
        payload = json.loads(authentication.decode_part(token.split(".")[1]))
        self.assertEqual(payload["exp"] - payload["iat"], 600)
        self.assertNotIn(token, err)
        entries = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(len(entries), 1)
        self.assertEqual(set(entries[0]), {"time", "status", "user_id"})
        self.assertEqual(entries[0]["status"], "login_success")
        self.assertEqual(entries[0]["user_id"], "TestUser")
        self.assertNotIn(token, self.log.read_text())
        self.assertNotIn(self.password, self.log.read_text())

    def test_wrong_password(self):
        self.assert_denied(["TestUser"], ["Incorrect login passphrase!"])
        entry = json.loads(self.log.read_text())
        self.assertEqual(set(entry), {"time", "status", "reason"})
        self.assertEqual(entry["reason"], "password_login_failed")

    def test_unknown_user_even_with_valid_credentials(self):
        credentials.create_credentials("Nobody", self.password)
        self.assert_denied(["Nobody"], [self.password])

    def test_missing_or_corrupt_credentials(self):
        path = credentials.credential_path("TestUser")
        path.unlink()
        self.assert_denied(["TestUser"], [self.password])
        path.write_text("broken JSON")
        self.assert_denied(["TestUser"], [self.password])

    def test_invalid_user_records(self):
        with mock.patch.object(issuer, "load_users",
                               return_value=({"TestUser": {}}, ["invalid"])):
            self.assert_denied(["TestUser"], [self.password])

    def test_cancelled_or_visible_input(self):
        for error in (EOFError(), KeyboardInterrupt(),
                      getpass.GetPassWarning("cannot hide input")):
            with self.subTest(error=type(error).__name__):
                self.assert_denied(["TestUser"], error)

    def test_invalid_arguments_never_prompt_or_sign(self):
        for arguments in (
            [], ["TestUser", "0"], ["TestUser", "3601"],
            ["TestUser", "1.5"], ["TestUser", "600", "extra"],
        ):
            with self.subTest(arguments=arguments):
                with mock.patch.object(issuer, "issue_token") as sign:
                    code, out, _, calls = self.run_login(arguments, [])
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertEqual(calls, 0)
                sign.assert_not_called()
        self.assertFalse(self.key.exists())

    def test_audit_failure_withholds_valid_token(self):
        with mock.patch.object(issuer, "write_audit_entry",
                               side_effect=OSError("private detail")):
            code, out, err, _ = self.run_login(["TestUser"], [self.password])
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertNotIn("private detail", err)

    def test_broken_audit_does_not_allow_failed_login(self):
        with mock.patch.object(issuer, "log_auth_failure",
                               side_effect=OSError("private detail")):
            self.assert_denied(["TestUser"], ["Incorrect login passphrase!"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
