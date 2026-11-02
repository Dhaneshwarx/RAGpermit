import contextlib
import getpass
import io
import unittest
from unittest.mock import patch

from src import reset_password as command


class ResetPasswordTests(unittest.TestCase):
    def run_reset(self, inputs, *, password_ok=True, admin_ok=True, error=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            prompt = stack.enter_context(patch.object(command.getpass, "getpass", side_effect=inputs))
            credentials = stack.enter_context(patch.object(command, "check_credentials", return_value=password_ok))
            stack.enter_context(patch.object(command, "is_admin", return_value=admin_ok))
            change = stack.enter_context(patch.object(command, "change", side_effect=error))
            audit = stack.enter_context(patch.object(command, "log_auth_failure"))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = command.main(["Deepak", "--admin", "Dhanesh"])
        for secret in ("Current private!", "New private!"):
            self.assertNotIn(secret, out.getvalue() + err.getvalue())
        return code, out.getvalue(), err.getvalue(), prompt, credentials, change, audit

    def test_success_uses_existing_audited_revocation_flow(self):
        code, out, _, prompt, credentials, change, _ = self.run_reset(
            ["Current private!", "New private!", "New private!"])
        self.assertEqual(code, 0)
        self.assertEqual(prompt.call_count, 3)
        credentials.assert_called_once_with("Dhanesh", "Current private!")
        change.assert_called_once_with("Dhanesh", {
            "action": "reset", "user_id": "Deepak", "password": "New private!"})
        self.assertIn("revoked", out)

    def test_invalid_admin_never_reaches_new_password_or_mutation(self):
        for credentials_ok, admin_ok in ((False, True), (True, False)):
            result = self.run_reset(["Current private!"], password_ok=credentials_ok, admin_ok=admin_ok)
            self.assertEqual(result[0], 1)
            self.assertEqual(result[3].call_count, 1)
            result[5].assert_not_called()
            result[6].assert_called_once_with("password_reset_auth_failed")

    def test_mismatch_and_invalid_lengths_never_change_credentials(self):
        for first, second in (("abc", "abd"), ("ab", "ab"), ("a" * 21, "a" * 21)):
            result = self.run_reset(["Current private!", first, second])
            self.assertEqual(result[0], 1)
            result[5].assert_not_called()

    def test_boundary_lengths(self):
        for size in (3, 20):
            result = self.run_reset(["Current private!", "a" * size, "a" * size])
            self.assertEqual(result[0], 0)
            result[5].assert_called_once()

    def test_hidden_input_failure_never_changes_credentials(self):
        for failure in (EOFError(), KeyboardInterrupt(), getpass.GetPassWarning()):
            result = self.run_reset([failure])
            self.assertEqual(result[0], 1)
            result[5].assert_not_called()

    def test_storage_failure_withholds_success_and_error_details(self):
        result = self.run_reset(["Current private!", "New private!", "New private!"],
                                error=OSError("private storage detail"))
        self.assertEqual(result[0], 1)
        self.assertEqual(result[1], "")
        self.assertNotIn("private storage detail", result[2])


if __name__ == "__main__":
    unittest.main()
