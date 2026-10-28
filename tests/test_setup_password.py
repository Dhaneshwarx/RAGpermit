import contextlib
import getpass
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import src.credentials as credentials
import src.setup_password as setup


class SetupPasswordTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "passwords"
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(
            mock.patch.object(credentials, "CREDENTIALS_DIR", self.root)
        )
        self.stack.enter_context(
            mock.patch.object(setup, "load_users",
                              return_value=({"TestUser": {}}, []))
        )
        self.password = "Temporary test passphrase!"

    def run_command(self, arguments, inputs):
        output, errors = io.StringIO(), io.StringIO()
        with mock.patch.object(setup.sys, "argv", ["setup_password"] + arguments):
            with mock.patch.object(setup.getpass, "getpass",
                                   side_effect=inputs) as prompt:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
                    code = setup.main()
        text = output.getvalue() + errors.getvalue()
        self.assertNotIn(self.password, text)
        return code, text, prompt.call_count

    def test_success_stores_hash(self):
        code, text, calls = self.run_command(
            ["TestUser"], [self.password, self.password]
        )
        self.assertEqual(code, 0)
        self.assertEqual(calls, 2)
        self.assertIn("No token was issued", text)
        self.assertTrue(credentials.check_credentials("TestUser", self.password))
        stored = credentials.credential_path("TestUser").read_text()
        self.assertNotIn(self.password, stored)

    def test_existing_credentials_are_preserved(self):
        credentials.create_credentials("TestUser", self.password)
        path = credentials.credential_path("TestUser")
        before = path.read_bytes()
        code, _, calls = self.run_command(["TestUser"], [])
        self.assertEqual(code, 1)
        self.assertEqual(calls, 0)
        self.assertEqual(path.read_bytes(), before)

    def test_unknown_user_never_prompts(self):
        code, _, calls = self.run_command(["Nobody"], [])
        self.assertEqual(code, 1)
        self.assertEqual(calls, 0)
        self.assertFalse(self.root.exists())

    def test_bad_arguments_never_prompt(self):
        for arguments in ([], ["TestUser", "password-on-command-line"]):
            with self.subTest(arguments=arguments):
                code, _, calls = self.run_command(arguments, [])
                self.assertEqual(code, 2)
                self.assertEqual(calls, 0)
        self.assertFalse(self.root.exists())

    def test_mismatch_and_short_password_save_nothing(self):
        for inputs in (
            [self.password, "Different test passphrase!"],
            ["short", "short"],
        ):
            with self.subTest(inputs=inputs):
                code, _, _ = self.run_command(["TestUser"], inputs)
                self.assertEqual(code, 1)
                self.assertFalse(self.root.exists())

    def test_cancelled_or_visible_input_saves_nothing(self):
        for error in (
            EOFError(), KeyboardInterrupt(),
            getpass.GetPassWarning("hidden input unavailable"),
        ):
            with self.subTest(error=type(error).__name__):
                code, _, _ = self.run_command(["TestUser"], error)
                self.assertEqual(code, 1)
                self.assertFalse(self.root.exists())

    def test_invalid_user_records_stop_setup(self):
        with mock.patch.object(setup, "load_users",
                               return_value=({"TestUser": {}}, ["bad record"])):
            code, _, calls = self.run_command(["TestUser"], [])
        self.assertEqual(code, 1)
        self.assertEqual(calls, 0)
        self.assertFalse(self.root.exists())

    def test_storage_failure_is_not_success(self):
        with mock.patch.object(setup, "create_credentials",
                               side_effect=OSError("private detail")):
            code, text, _ = self.run_command(
                ["TestUser"], [self.password, self.password]
            )
        self.assertEqual(code, 1)
        self.assertNotIn("private detail", text)
        self.assertNotIn("credentials created", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
