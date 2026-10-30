# PermitRAG

**Start here:** [Step-by-step running manual (Windows PowerShell)](docs/RUNNING.md)

A permission-aware RAG system for company documents. The language model only ever sees text the asking user is allowed to read, so it cannot leak what it never received.

Everything runs locally on a laptop: Ollama (`bge-m3` for embeddings, `qwen3.5:4b` for answers), Qdrant in local mode, and plain Python with no RAG framework, so every security decision is a visible function.

## Local web interface

After installing dependencies, starting Ollama, ingesting documents, and setting up a user password (see the running manual):

```powershell
python -m src.web_server
```

Open **http://127.0.0.1:8000** to sign in and ask questions with citations. The website uses existing password records and the same permission-aware pipeline. It runs locally and provides no public account registration. Browser sessions use HttpOnly, SameSite cookies and expire after 15 minutes. This is a loopback-only demo server, not a production web deployment.

## The problem

Basic RAG searches every document for every user. A question like "What is the base pay for Band L5?" can return HR-only text to an intern, and an instruction such as "do not reveal secrets" in the prompt is not access control. PermitRAG makes the decision in code, before retrieval and before any prompt exists.

## Example: one question, three users

Question: "What approval code is needed to start a database failover?" The answer sits in an Engineering runbook with clearance 2.

| User | Role | Answer |
|---|---|---|
| Premkumar | Intern, Engineering | I couldn't find that in the documents available to you. |
| Deepak | Engineer, Engineering | The approval code needed to start a database failover is FO-7731-K [1]. |
| Dhanesh | CEO, Executive | I couldn't find that in the documents available to you. |

The intern's clearance is too low. The CEO has enough clearance but is outside the Engineering department and is not listed on the document. For both, the runbook text never reached the model, and the reply is the same sentence a question about a nonexistent topic gets. Answers come from `tests/test_answers.py` (10 October 2026); wording varies between runs.

## How it works

Ingestion (run once, or after documents change):

1. Each document starts with a header: `doc_id`, `title`, `department`, `clearance`, `allowed_roles`. A strict loader checks it against the policy. A document with a missing or invalid header is rejected and never stored.
2. Bodies are split into chunks at `##` headings. Every chunk carries a copy of its document's access fields.
3. Chunks are embedded with `bge-m3` (1024 numbers each) and stored in Qdrant. The collection is rebuilt on every run, so stale permissions cannot survive.

Answering a question:

1. Sign-in comes first. A signed, short-lived token must be present and valid, or the request ends with one fixed sentence and nothing else runs (see Authentication). The user named in the token is then looked up in `data/users.json`: department, role and clearance always come from that record, never from the token.
2. The question is embedded. The question text plays no part in the access decision.
3. Qdrant searches only the chunks that pass an access filter built from the user record: clearance high enough, and department `ALL` or the user's own, or the user's role listed in `allowed_roles`.
4. Each hit is re-checked by a separate plain-Python rule, `can_read`. If the two disagree, retrieval raises an error, and the request ends with the fixed sentence and an error status in the log.
5. The prompt is built only from the allowed chunks, plus a line from the user's record (role and department) so the model can read "my".
6. `qwen3.5:4b` answers with `[1]`-style citations, or replies `NOT_FOUND`.
7. Code, not the model, turns `NOT_FOUND`, no chunks, an unknown user, or any error into one fixed sentence: "I couldn't find that in the documents available to you."
8. The request is appended to `logs/audit.jsonl`: user, question, status, chunk ids retrieved, sources cited. No answers and no chunk text. If the log cannot be written, the answer is withheld.

## Security design

| Stage | What it does | Where |
|---|---|---|
| Authentication | Who is asking. A signed, short-lived token must be valid, or nothing else runs. | `src/authentication.py`, `src/ask.py` |
| Token issuer | Verifies a local password, signs a short-lived token, and withholds it if audit logging fails. | `src/issue_token.py`, `src/credentials.py`, `src/passwords.py` |
| MCP front door | How an AI app asks. Sign-in first, one input, a rate limit, then the same pipeline. It decides nothing about who may read what. | `src/mcp_server.py` |
| Authorization | Decides what a user may read, from the user record only. | `src/authorization.py` |
| Retrieval | Applies that decision inside the vector search. | `src/retrieval.py` |
| Prompt generation | Builds the prompt from allowed chunks only. | `src/answering.py` |
| LLM generation | Writes the answer. Has no authority and writes no refusals. | `src/answering.py` |
| Audit | Records what happened on every request, with ids only. | `src/audit.py` |

The rules are written in `data/POLICY.md`: deny by default, fail closed, the same reply for "restricted" and "does not exist", and restricted text is never placed in a prompt.

## Authentication

Who is asking is decided by a signed token, checked before anything else runs. The rules are section 6 of `data/POLICY.md`.

- A token has three parts joined by dots: header, payload, signature. The signature is HMAC-SHA256 under a secret key in `keys/token_key.txt`, so nobody can change a token or invent one without the key. The code uses only Python's standard library.
- The payload holds only `sub` (the user id), `iat` (issued at) and `exp` (expires at). Department, role and clearance still come from `data/users.json` on every request, so changing or removing a user takes effect at once.
- A token is accepted only if every check passes: three well-formed parts, algorithm exactly HS256, a signature that matches the exact text, a `sub` that is text, whole-number `iat` and `exp`, not issued in the future, not expired, and at most one hour of life.
- Every failure gets the same reply, "Authentication failed. Please sign in.", and causes no store access, embedding, search or model call. The log records `auth_failed` and a short reason code, never the token, a name taken from it, or the question.
- The checker never creates a key. `src/issue_token.py` does, once, and never replaces an existing one. Replacing the key invalidates every token at once.

### Local password setup and login

A trusted local administrator creates initial credentials with `python -m src.setup_password <user_id>`. There is no default password. Setup accepts only known users with valid user records, asks for the password twice, and refuses to overwrite existing credentials.

- Passwords contain 15-128 characters. Spaces and case are preserved exactly.
- Credentials use PBKDF2-HMAC-SHA256 with 600,000 iterations, a random 16-byte salt, and a 32-byte derived hash. Password comparisons use `hmac.compare_digest`.
- Records live under `keys/passwords/`, which is excluded by the existing `keys/` Git ignore rule. They contain a user ID and hashing metadata, never a plaintext password.
- `python -m src.issue_token <user_id> [seconds]` asks for a hidden password, checks the credentials and current user records, and issues a token only on success. It does not accept passwords as command arguments.
- Failed login returns the same authentication-failure message and attempts to log `password_login_failed`. Successful issuance must log `login_success` before the token is printed; a logging failure withholds the token.
- `tests.mcp_probe` uses the password-protected issuer before starting the MCP server.

Hidden input normally displays no letters or stars. Run each interactive command separately and wait for its prompt before entering a password. See the Windows input limitation below for the unresolved behavior observed during local verification.

## MCP: asking from an AI app

MCP (Model Context Protocol) lets an AI app such as Claude Desktop or Claude Code run a tool on your computer. `src/mcp_server.py` is that tool. The rules are section 7 of `data/POLICY.md`.

- **One tool, one input.** The tool is `ask_documents` and its only input is `question`. There is no input for a user, a role, a clearance or a token, so a model that hostile text has steered cannot ask for more than the signed-in person may read.
- **Who is asking comes from the environment.** The server reads the signed token from `PERMITRAG_TOKEN` on every call and checks it exactly as `src/ask.py` does. Authentication is checked fresh on every call, so an expired token is rejected on the next call. The server retains handshake state and rate-limit history. One server serves one person.
- **A front door, not a new rulebook.** After sign-in it checks the input (1 to 2000 characters, nothing else accepted) and applies a limit of 20 questions in 60 seconds. Then it hands over to the same pipeline as `src/ask.py`: user record, authorization, retrieval, prompt, model, audit log.
- **Failures say nothing.** A failed sign-in, a bad input, the limit and a system failure each get one fixed sentence, marked as an error. No cause, path or stack trace leaves the server. Standard output carries protocol messages only.
- **Plain code.** The protocol is spoken with Python's standard library, so every rule is a visible line. It speaks the older handshake (versions 2024-11-05 to 2025-11-25) and the newer 2026-07-28 form. A production server would use the official SDK.

Try it without any AI app after setting up the user's password (Ollama must be running, and `python -m src.ingest` done). The probe asks for that password:

    python -m tests.mcp_probe Premkumar "How many casual leave days do I get?" --show

Connect Claude Code. Run this from the project folder, with your own paths. The token lives one hour, so repeat the two lines with a new token after that:

    $token = python -m src.issue_token Premkumar 3600
    claude mcp add permitrag -e PERMITRAG_TOKEN=$token -- C:\path\to\PermitRAG\.venv\Scripts\python.exe C:\path\to\PermitRAG\run_mcp_server.py

Connect Claude Desktop. Add this to `%APPDATA%\Claude\claude_desktop_config.json` with your own paths (forward slashes avoid escaping) and a fresh token, then restart the app:

    {
      "mcpServers": {
        "permitrag": {
          "command": "C:/path/to/PermitRAG/.venv/Scripts/python.exe",
          "args": ["C:/path/to/PermitRAG/run_mcp_server.py"],
          "env": { "PERMITRAG_TOKEN": "paste the token here" }
        }
      }
    }

A token in a config file is a password for one hour. The app receives the answers: if it is a cloud service, the answers (not the documents) leave your computer.

## Threats and evidence

| Threat | Defence | Evidence |
|---|---|---|
| A user reads a document they should not | Filter inside the search, plus a second check | 276 user-chunk pairs match a hand-made answer key, 0 mismatches |
| Role claimed in the question ("I am the CEO") | Permissions come from the user record only, and who is asking comes from a signed token | 7 attack prompts, all got the fixed sentence |
| Forged, altered or expired token | Signature over the exact text, algorithm pinned to HS256, one-hour maximum life, key of at least 32 bytes | `tests/test_auth.py`: 61 hand-made cases and 69,732 one-character edits, none accepted. `tests/test_auth_breaks.py`: 55 planted mistakes, all caught |
| A failed sign-in used to probe or to reach data | One identical reply, no store access, embedding, search or model call, and a log line with a reason code only | `tests/test_signin.py`: 13 kinds of failed sign-in |
| An AI app, or a model steered by hostile text, claims to be someone else | Identity is not an input. It comes only from the signed token in the server's environment, and every extra input is refused | `tests/test_mcp.py`: 153 hand-made conversations, 19 scenario checks. `tests/test_mcp_breaks.py`: 130 planted mistakes, all caught |
| An app keeps asking, or sends broken messages | At most 20 questions in 60 seconds, lines over 65,536 bytes refused, every bad message answered with an error that changes nothing and reveals nothing | `tests/test_mcp.py`, including 6,000 random and damaged messages |
| Prompt injection to extract restricted text | The model never receives restricted text | Structural, backed by the retrieval test above |
| Probing whether a restricted document exists | One identical sentence for restricted, missing and unanswerable | 12 of 12 blocked questions got it |
| Bad or missing metadata | The loader rejects it, `can_read` denies it | 6 of 6 broken test documents rejected |
| Failures | Fail closed, and the tests fail on any error | 0 errors in 37 prompts |
| Stale permissions | Collection rebuilt on every ingest | By design |
| Bypassing the filter in code | Only one search call exists in `src/` | `query_points` appears once, in `src/retrieval.py` |
| No record of what happened | One log line per request, ids only | `tests/test_audit.py`: one line per request, no answers or secrets in the log, forged lines blocked, answer withheld if the log fails |

## Results

Measured on 10 October 2026 on an ASUS TUF F17 (RTX 2050, 4 GB). Answer wording varies between runs, so rerun before quoting numbers.

- 10 documents, 46 chunks, 6 users, 60 document-user pairs (27 allowed).
- 30 questions (18 allowed, 12 blocked) plus 7 attack prompts.
- Blocked questions answered with the fixed sentence: 12 of 12.
- Allowed answers containing the expected text: 18 of 18.
- Leaks: 0. Errors: 0.
- Audit checks: all pass.
- Authentication checks: all pass. 61 hand-made token cases, 69,732 one-character edits (none accepted), 55 planted mistakes (all caught).
- Sign-in checks: all pass. 13 kinds of failed sign-in got the same reply, with no store access, embedding, search or model call.
- MCP front-door checks: all pass. 153 hand-made conversations, 19 scenario checks, 6,000 random and damaged messages, a real process started from another folder, and 130 planted mistakes (all caught).

### Verification on 28 October 2026

The local rerun passed the access matrix (60 pairs, 27 allowed), authentication (61 cases and 69,732 rejected token edits), all 55 authentication mutations, sign-in, MCP (153 conversations, 19 scenarios, 6,000 damaged/random inputs), and all 130 MCP mutations. Retrieval checked 276 user-chunk pairs with no mismatches; all 18 allowed questions found their sources. Answer tests found the expected text in all 18 allowed answers, the fixed refusal in all 12 blocked answers, and refusals for all 7 attack prompts, with no reported errors or detected leaks. Audit checks passed.

Password tests also passed: 8 hashing tests, 8 setup tests, and 9 login tests. A live authenticated MCP call returned 12 casual leave days with the `leave-policy / Casual leave` source and exited with code 0.

That live call used a temporary input workaround: PowerShell masked input supplied the password to the issuer's normal credential checks and audit flow, then the resulting token was used by a small MCP client. The unmodified interactive password prompt and complete interactive probe flow did not pass this session; see Limitations. This was not a fresh-clone or external AI-client test of the password update.

A leak in these results means a secret string from a document the user cannot read appeared in an answer or citation.

## Limitations

- **Local trust boundary.** The CLI now checks passwords, but anyone with access to the signing key or control of the application code can bypass that CLI. Initial password setup is a trusted administrator operation, not public registration. Windows filesystem permissions protect credential files; Git ignore rules do not enforce access control. There is no per-token revocation: replacing the key ends every token at once. Production would use a vetted authentication library and managed identity or single sign-on.
- **Windows interactive input remains unresolved.** During the 28 October verification, Python's hidden prompt repeatedly received empty entries; other attempts received text. The cause has not been established. Stored credentials and token issuance worked with a temporary PowerShell input workaround, but ordinary interactive setup/login and the full probe must be rechecked before claiming the Windows login experience works end to end.
- **Password lifecycle is limited.** There is no supported password-reset command, login-attempt rate limit, account lockout, or multifactor authentication. Changing a password does not revoke already-issued tokens.
- **An AI app asks as the signed-in person.** Everything that person may read can be reached through the app, including by a model that hostile text has steered. The defence is the choice of person, not a prompt. If the app is a cloud service, the answers it receives (not the documents) leave your computer.
- **MCP tokens cannot be renewed by the server.** A token lasts at most one hour. After that every call gets the sign-in sentence until the server is started again with a new token. One server serves one person, and questions are handled one at a time.
- **Slow answers.** Some AI apps give up on a tool after about a minute. A small model on a plain computer can need longer.
- **MCP in plain code.** The protocol is handled by hand-written code, so every rule is visible. It was verified with the repository's MCP tests and local probe, including live Ollama and Qdrant requests. Compatibility with external AI apps has not been verified in this test run.
- **Small, synthetic data.** 10 documents and 30 questions, all written by the author. The 18 of 18 figure describes this set only.
- **Weak quality checks.** Allowed answers are checked by looking for expected text, not by a human or an evaluation framework.
- **The leak scan matches exact strings.** A paraphrased secret would pass it. The structural tests above are the real evidence.
- **Documents are trusted.** Instructions hidden inside a document are not tested.
- **Plain-text store.** `qdrant_data/` holds every chunk, restricted ones included, unencrypted. Qdrant local mode lets only one program open it at a time.
- **The audit log is a plain file.** Anyone with file access can edit it, and it holds questions and chunk ids, so `logs/` is sensitive and is not published.
- **CLI failures.** Internal result statuses are hidden. Store and user-loading failures return the fixed refusal without a traceback; diagnostic request statuses belong in the local audit log.
- **Basic retrieval.** Dense search only, top 4 chunks, no reranker, no conversation memory.
- **Personal questions are lightly tested.** The model is told the asker's role so it can read "my". That fixed one failing question, but it could also over-match a role to similar text.

## Project layout

    data/POLICY.md          access rules in plain English
    data/users.json         demo users
    data/docs/              10 fictional documents with access headers
    src/policy_values.py    the one list of valid departments, roles and clearances
    src/document_loader.py  strict header parsing and validation
    src/chunker.py          sections to chunks
    src/vector_store.py     Qdrant local store
    src/ingest.py           load, chunk, embed, store
    src/authorization.py    user records and the can_read rule
    src/retrieval.py        filtered search
    src/answering.py        prompt, model call, fixed refusal
    src/audit.py            append-only request log
    src/authentication.py   checks sign-in tokens
    src/issue_token.py      verifies a password, signs a token, logs issuance
    src/passwords.py        password hashing and verification
    src/credentials.py      local credential storage
    src/setup_password.py   trusted initial setup; preserves existing credentials
    src/ask.py              command-line entry point, needs a valid token
    src/mcp_server.py       the MCP front door: one tool, sign-in first, then the same pipeline
    run_mcp_server.py       starts the MCP server from any folder
    src/smoke_test.py       checks that both Ollama models respond
    tests/access_matrix.csv hand-made answer key (60 cells)
    tests/questions.json    30 test questions
    tests/token_cases.csv   hand-made answer key for tokens (61 cases)
    tests/token_builders.py builds test tokens without using the checker's code
    tests/mcp_cases.json    hand-made answer key for the MCP server (153 conversations)
    tests/mcp_probe.py      a small MCP client for trying the server by hand
    tests/test_*.py         loader refusals, access matrix, retrieval, answers, audit,
                            tokens, planted mistakes, sign-in, the MCP server and its planted mistakes
    qdrant_data/            generated by ingest, not published
    logs/audit.jsonl        generated at run time, not published
    keys/token_key.txt      signing key, created by the issuer, not published
    keys/passwords/         local password hashes and salts, not published

## Portfolio and verification

See [the portfolio guide](docs/PORTFOLIO.md) for an interview demo and resume wording. Run `python -m tests.run_all` for all offline checks, or add `--live` to include local Ollama retrieval, answer and audit checks. GitHub Actions runs offline checks on Windows and Linux.

## Run it (Windows PowerShell)

Install Ollama and start it. Then clone the repository and open its folder:

    git clone https://github.com/Dhaneshwarx/RAGpermit.git
    cd RAGpermit

Then, from that folder:

    python -m venv .venv
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    ollama pull bge-m3
    ollama pull qwen3.5:4b
    python -m src.ingest
    python -m src.setup_password Premkumar
    $env:PERMITRAG_TOKEN = python -m src.issue_token Premkumar
    python -m src.ask "How many casual leave days do I get?"

Run these commands one at a time. Password setup is needed once per user: choose a private 15-128 character password and enter it twice. It refuses to replace an existing credential record. The issuer then asks for that password, creates the signing key (`keys/token_key.txt`, never published) if missing, and returns a token valid for 15 minutes. Only continue to `src.ask` if issuance succeeds. Sign out with `Remove-Item Env:PERMITRAG_TOKEN`.

The Windows interactive-input issue described above remains open. Do not treat the successful automated tests as verification of these interactive steps on every terminal.

Tests (`test_retrieval`, `test_answers` and `test_audit` need Ollama running; the others work offline):

    python -m tests.test_loader_refusals
    python -m tests.test_access_matrix
    python -m tests.test_retrieval
    python -m tests.test_answers
    python -m tests.test_audit
    python -m tests.test_auth
    python -m tests.test_auth_breaks
    python -m tests.test_signin
    python -m tests.test_mcp
    python -m tests.test_mcp_breaks
    python -m unittest -v tests.test_passwords
    python -m unittest -v tests.test_setup_password
    python -m unittest -v tests.test_password_login

Tested with Python 3.12.3, Ollama 0.35.1, `ollama` 0.6.3 and `qdrant-client` 1.19.1.

## Roadmap

Resolve and reverify Windows interactive password entry, add password reset and login-attempt controls, token renewal for the MCP server, hybrid search with a reranker, PII redaction on answers, RAGAS evaluation, and scanned-document ingestion.
