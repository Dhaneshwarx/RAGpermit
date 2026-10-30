# Verification: 30 October 2026

Environment: existing Windows checkout, Python virtual environment, local Ollama models and previously ingested Qdrant collection. This is not a clean-machine installation test.

Live checks passed:
- Retrieval: 276 user/chunk pairs, zero permission mismatches; all 18 authorized questions found their expected source.
- Answers: 18/18 expected-text matches, 12/12 fixed refusals, seven attack prompts refused; no errors or exact-string leaks detected.
- Audit: request logging, log-injection protection and withholding answers on logging failure passed.

Password hashing/setup/login: 25 tests passed. New CLI store/user failure regression passed. Internal statuses are no longer printed to users.

The first combined run flagged existing tests that expected the removed diagnostic status line. Those output expectations were updated; the underlying authorization and audit assertions remain in place.

Remaining boundaries: Windows interactive password entry needs verification in the user's terminal; external AI-client compatibility is not verified; no production deployment, SSO, password reset or token revocation service is claimed. See README for the full limitations.

Final offline rerun: all suites passed (exit code 0), including 26 unittest cases, loader refusals, 60 access pairs, 61 token cases, 69,732 rejected token edits, 55 authentication mutations, sign-in checks, 153 MCP conversations, 19 MCP scenarios and 130 MCP mutations. The restricted execution environment initially blocked a temporary-key rename; the approved unrestricted rerun passed. Hosted GitHub Actions results have not been verified in this session.
