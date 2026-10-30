# PermitRAG running manual (Windows PowerShell)

PermitRAG runs in a terminal. It does not currently have a web interface. Run commands from the project folder, one at a time. Password prompts must finish before you run the next command.

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

Enter a private password containing 15-128 characters, then enter it again. No characters or stars appear while typing. There is no default password. If credentials already exist, skip setup and use the existing password. Setup intentionally refuses to overwrite credentials. There is currently no supported password-reset command.

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
