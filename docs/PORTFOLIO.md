# Portfolio demo

PermitRAG is a local security-focused RAG prototype, not a production identity service.

## Run

Follow the README installation and password setup instructions. Ollama must be running with `bge-m3` and `qwen3.5:4b`, and `python -m src.ingest` must have completed.

Run `python -m tests.run_all` for offline verification and `python -m tests.run_all --live` for retrieval, answer and audit evaluation. Live tests use the local models and take longer. Exit code zero means all requested suites passed. CI runs the offline suite on Windows and Linux; it does not measure model quality.

## Demonstrate in an interview

1. Explain the trust boundary: identity comes from a signed token; permissions come from the current user record.
2. Sign in as Premkumar using `python -m src.issue_token Premkumar` and capture the token in `PERMITRAG_TOKEN` as shown in the README.
3. Ask `python -m src.ask "How many casual leave days do I get?"` and show the answer and citation.
4. Ask `python -m src.ask "What approval code is needed to start a database failover?"`. The intern should receive the fixed refusal.
5. Sign in as Deepak and repeat the failover question. Show the authorized answer and citation.
6. Explain how Qdrant filters before retrieval and the independent Python rule rechecks every returned chunk.
7. Show test results. Do not display tokens, password files, signing keys, or private audit logs in recordings.

Create each user's password locally before the demonstration. No default passwords are shipped. The unresolved terminal-specific password input issue is documented in README; verify interactive login in your own terminal before recording.

## Resume wording

Built PermitRAG, a local permission-aware document Q&A system using Python, Ollama and Qdrant, with signed-token authentication, password hashing, pre-retrieval access filters, citation-backed answers and fail-closed audit logging. Implemented automated authorization, token-tampering and MCP protocol regression tests with Windows/Linux CI.

Use measured accuracy figures only alongside the evaluation date and synthetic dataset size. Do not describe exact-string leak checks as proof that all possible leaks are prevented.
