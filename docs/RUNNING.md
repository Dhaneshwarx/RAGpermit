# PermitRAG running manual (Windows PowerShell)

PermitRAG includes a local web interface and a terminal interface. Run commands from the project folder, one at a time. Password prompts must finish before you run the next command.

## 1. Requirements

Install Python 3.12, Git, and Ollama. Open the Ollama application before continuing. Qdrant runs inside Python; no separate Qdrant server or Docker installation is needed.

## 2. Get the project

For a new installation:

```powershell
git clone https://github.com/Dhaneshwarx/RAGpermit.git
cd RAGpermit
python -m venv .venv
```

If you already have the project, open its existing folder instead. For example, on the author's computer:

```powershell
cd C:\Users\Dhanesh\PermitRAG
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow scripts for this terminal session and try again:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

Install dependencies on first setup:

```powershell
python -m pip install -r requirements.txt
```

## 3. Prepare the local models

With Ollama running:

```powershell
ollama pull bge-m3
ollama pull qwen3.5:4b
ollama list
```

Downloads are required only when the models are missing. Both model names should appear in the list.

## 4. Index the documents

```powershell
python -m src.ingest
```

This embeds the documents and rebuilds the local collection. Run it on first setup and whenever documents or their permissions change. The supplied dataset contains 10 fictional documents and produces 46 chunks. Close other PermitRAG processes before rebuilding: Qdrant local storage can be opened by only one process at a time.

## 5. Create a local password

Run this once for the demo user:

```powershell
python -m src.setup_password Premkumar
```

Enter a private password containing 3-20 characters, then enter it again. No characters or stars appear while typing. There is no default password. If credentials already exist, skip setup and use the existing password. Setup intentionally refuses to overwrite credentials. Existing passwords can be reset with the authenticated terminal command described below.

## Use the web interface

After completing steps 1-5, start the local website:

```powershell
python -m src.web_server
```

Open **http://127.0.0.1:8000** in your browser. Enter your user ID and password, then ask questions on the workspace page. Answers include available citations. Use **Sign out** to clear the browser session. Keep the terminal open while using the website; press Ctrl+C to stop it.

The browser login uses the same local password records, so it avoids the terminal password prompt during everyday login. Initial account setup still requires step 5. Accounts cannot be registered through the website: permissions are assigned by the local administrator.

The server listens only on your computer. It is a local demo server, not a public deployment. Sessions last 15 minutes; login is limited to 10 attempts per minute and questions to 20 per minute across this local server. Sign-out clears the cookie and revokes that session token. Do not expose this HTTP server through a public tunnel.

### Follow-up questions

The web chat sends your last three successful user questions with the next question. For example, ask "What is Project Horizon?" and then "When is its deadline?" when your workspace has a document about that project. The server searches again using your current account permissions and answers from retrieved documents. Earlier questions help resolve references; they do not supply facts or grant access. Earlier assistant answers are not included, so repeat a name if it appeared only in an answer.

Select **New conversation** to clear the visible conversation and question context. Context also clears on page reload, sign-out, a new sign-in, and when a request detects an expired session or an account change. History lives only in the current tab's memory; the existing server audit log can record the beginning of the contextual question. The terminal and MCP interfaces remain single-question interfaces.

Optional browser-script behavior checks (Node.js required only for this developer check):

```powershell
node tests/test_conversation_ui.cjs
```

The following terminal sign-in steps are an alternative to the web interface.

## 6. Sign in

```powershell
$env:PERMITRAG_TOKEN = python -m src.issue_token Premkumar
```

Enter the password. Continue only if the command succeeds and reports the token lifetime. If it fails, clear the variable before retrying:

```powershell
Remove-Item Env:PERMITRAG_TOKEN -ErrorAction SilentlyContinue
```

The default token lasts 15 minutes. Repeat sign-in after expiry. Never publish the token or include it in screenshots.

## 7. Ask questions

An allowed question:

```powershell
python -m src.ask "How many casual leave days do I get?"
```

Expected: an answer about 12 casual leave days, with a citation. Exact wording may vary.

A restricted question:

```powershell
python -m src.ask "What approval code is needed to start a database failover?"
```

Expected for Premkumar:

> I couldn't find that in the documents available to you.

To demonstrate a different permission level, set up Deepak's password once, sign in as Deepak, and repeat the question:

```powershell
python -m src.setup_password Deepak
$env:PERMITRAG_TOKEN = python -m src.issue_token Deepak
python -m src.ask "What approval code is needed to start a database failover?"
```

Deepak is authorized to read that runbook and should receive an answer with a source.

## 8. Sign out

```powershell
Remove-Item Env:PERMITRAG_TOKEN -ErrorAction SilentlyContinue
```

This removes the token from this terminal; it does not revoke copies held elsewhere.

## Everyday startup

After initial setup, open PowerShell, move to your project folder, activate the environment, open Ollama, then run:

```powershell
$env:PERMITRAG_TOKEN = python -m src.issue_token Premkumar
python -m src.ask "How many casual leave days do I get?"
```

You do not need to reinstall dependencies, download models or rebuild the index unless something changed.

## Verify the project

Offline security and regression tests:

```powershell
python -m tests.run_all
```

Include real retrieval, model answers and audit checks (Ollama must be running and ingestion completed):

```powershell
python -m tests.run_all --live
```

The tests can take several minutes. Success ends with `All requested suites passed.` See [verification results](VERIFICATION.md) for the measured environment and limitations.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Python or Git is not recognized | Install it, ensure it is on PATH, and reopen PowerShell. |
| A Python package is missing | Activate `.venv`, then install `requirements.txt`. |
| Ollama connection fails | Open the Ollama app and retry `ollama list`. |
| A model is missing | Run the corresponding `ollama pull` command above. |
| Authentication fails | Check the user ID and password, then issue a fresh token. |
| Credentials already exist | Skip setup and use the existing password. |
| Password input arrives empty | Try a normal standalone PowerShell terminal and run each command separately. Terminal-specific hidden input remains unresolved; report the terminal and error without sharing credentials. |
| Storage is locked | Stop other PermitRAG CLI or MCP processes and retry. |
| An allowed question gets the fixed refusal | Check that Ollama is running, both models exist, and ingestion succeeded. The app deliberately uses the same refusal for unavailable answers and internal errors. |

## Optional: connect an AI app

See [MCP setup in the README](../README.md#mcp-asking-from-an-ai-app). The local probe and protocol tests are verified; external AI-client compatibility remains unverified.

Keep `keys/`, `logs/`, `.venv/` and `qdrant_data/` out of GitHub. They are already excluded by `.gitignore`.

## Administrator document management

In a private workspace, data/admins.json contains a JSON array of approved administrator user IDs. Existing CEO status does not grant administration automatically. Dhanesh's private administrator setup was performed locally; no private administrator list is included in the repository.

Sign in as an administrator and open Manage documents on the question page. Refresh to list documents, select one to edit, or import a permission-tagged Markdown file (maximum 200 KB). Its header doc_id must match the document ID field. Save or delete, then choose Rebuild index. Uploads currently support UTF-8 Markdown with the existing access header; plain .txt, PDF and Word import are not implemented.

After a web document change, all question interfaces refuse retrieval until rebuilding succeeds. This pending state survives a restart. A failed rebuild keeps questions blocked. Deleting all documents and rebuilding clears the collection. Editing files outside this interface still requires explicit ingestion and operational care. The server handles one request at a time; indexing may take several minutes.

Administrator access includes viewing and editing full source documents across departments. Only grant this capability to trusted document administrators. It does not change their question-answering permissions.


## Manage users

Restart the server after updating the application. Sign in as an administrator, expand Manage users, and select Refresh users. Select an account to edit, or choose New account and enter a unique ID. Choose role, department and clearance explicitly. Create/reset requires a password of 3-20 characters; the form clears it after submission. Passwords are never returned or included in audit entries.

Update access, Reset password, Disable account and Revoke sessions end existing sessions for the affected account. Disable removes the active record; it does not delete their documents. Creating the same ID again resets its password and revokes earlier tokens. The panel cannot change the administrator allowlist or disable/reassign administrator accounts. Existing private accounts and passwords are unchanged until you submit an operation.

Browser sign-out revokes its current token. Account revocation applies across web, CLI and MCP and persists across server restarts. Backups must preserve the private keys/revocations.sqlite3 database alongside other account state. All processes must run the updated version for revocation enforcement.


Password policy update: new and reset passwords contain 3-20 characters. Existing passwords up to 128 characters remain valid for login until reset. Reset Deepak, Arjun and Kavin first, then reset Dhanesh last because the administrator's own reset ends that session. Enter secrets only in the password field. Prefer the longer end of the permitted range.


## Reset an existing password in the terminal

The reset command requires the current password of a configured administrator. It then asks for the new password twice, using hidden input. Passwords are never command arguments. New passwords contain 3-20 characters; existing longer administrator passwords are accepted for authentication. No default passwords are provided.

In PowerShell, from the project folder:

```powershell
$env:PERMITRAG_WORKSPACE = "C:\Users\Dhanesh\PermitRAGPrivate"
.\.venv\Scripts\python.exe -m src.reset_password Deepak --admin Dhanesh
```

In Windows Command Prompt (cmd.exe), set the workspace with `set PERMITRAG_WORKSPACE=C:\Users\Dhanesh\PermitRAGPrivate` instead. The Python command is the same.

Run separately for Deepak, Arjun and Kavin. Reset Dhanesh last using `python -m src.reset_password Dhanesh --admin Dhanesh`. Each command first asks for the current Dhanesh password, then the new target password and confirmation. Existing target sessions are revoked on reset. After resetting Dhanesh, use the new administrator password for later commands. Initial setup remains `src.setup_password`; it intentionally refuses to overwrite existing credentials.

If hidden input is unavailable, the reset command stops rather than echoing passwords. A storage failure can revoke sessions even when password replacement does not complete; retry after fixing storage. This is an account-management command, not a recovery bypass for an unknown administrator password.
