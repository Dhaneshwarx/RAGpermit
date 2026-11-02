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

## Web interface verification

The local web interface adds password login, an HttpOnly/SameSite session cookie, a question page with citations, and sign-out. Six HTTP regression tests pass: static route allowlisting, cross-origin request rejection, authentication before store access, withholding cookies on audit failure, rejecting identity overrides and hiding internal answer statuses, and login rate limiting/logout. The tests use mocked model/credential dependencies; the earlier live pipeline evaluation is separate. Browser visual verification was unavailable because the browser tool failed to initialize on this machine.

## 31 October 2026: document administration

Implemented private-workspace storage, a separate administrator allowlist, and browser document import/edit/delete/reindex controls. Pending web changes block retrieval across web, CLI and MCP until an administrator rebuild completes. The empty-collection rebuild clears old points. UTF-8 BOM document loading is supported.

Validation: 32 focused unit tests and 8 HTTP tests passed. These include unauthorized administrator routes, invalid metadata/path rejection, failed rebuild protection, and clearing an empty collection. Browser visual QA and live embedding/answer evaluation of the new administration workflow were not performed in this session. Earlier model evaluation results apply to their stated datasets only.

Remaining: user-management UI and password reset, revocable sessions, improved summaries/follow-up retrieval, backup/restore verification, company-network deployment and public hosting. The application remains a local prototype; this milestone does not complete all project requirements.

## 1 November 2026: accounts and revocation

Added administrator account creation, access updates, password reset, disabling and explicit session revocation. Administrator accounts cannot be disabled or reassigned in the panel. Persistent token-digest revocation and per-user issuance cutoffs apply to web, CLI and MCP. Revocation-store failures deny authentication. No existing private account/password was modified by this implementation.

Validation: 32 focused unit tests and 9 HTTP tests passed. Sign-in checks passed. MCP checks passed: 153 conversations, 19 scenarios, 6000 damaged/random messages and real-process checks. JavaScript syntax and Python compilation passed. Browser visual verification and a live user-management walkthrough remain unverified. Network/public deployment remains unfinished.
# Manual release note (2 November 2026)

The measurements below are historical. For the extractive evidence release, see the handoff package's VERIFICATION.md and [manual](MANUAL_FINISH.md). It adds strict evidence selection and exact-section lookup; earlier model-answer quality figures are not measurements of this version.

