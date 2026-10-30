"""CLI errors must not disclose internal details."""
import contextlib
import io
import unittest
from unittest.mock import patch
from src import ask
from src.answering import REFUSAL


class CliFailureTests(unittest.TestCase):
    def test_store_and_user_failures_are_generic_and_audited(self):
        for failing in ('load_users', 'open_store'):
            with self.subTest(failing=failing), contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(ask.sys, 'argv', ['ask', 'question']))
                stack.enter_context(patch.object(ask.authentication, 'authenticate', return_value=('user', None)))
                stack.enter_context(patch.object(ask, 'load_users', return_value=({'user': {}}, [])))
                stack.enter_context(patch.object(ask, failing, side_effect=RuntimeError('private path')))
                audit = stack.enter_context(patch.object(ask, 'write_audit_entry'))
                answer = stack.enter_context(patch.object(ask, 'answer_question'))
                screen = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                self.assertEqual(ask.main(), 1)
                self.assertEqual(screen.getvalue(), REFUSAL + '\n')
                audit.assert_called_once()
                answer.assert_not_called()
