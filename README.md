# PermitRAG

A permission-aware RAG system for company documents. The language model only ever sees text the asking user is allowed to read, so it cannot leak what it never received.

Everything runs locally on a laptop: Ollama (`bge-m3` for embeddings, `qwen3.5:4b` for answers), Qdrant in local mode, and plain Python with no RAG framework, so every security decision is a visible function.

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

1. The user is looked up in `data/users.json`. This is a stand-in for login (see Limitations).
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
| Authentication | Who is asking. Currently a stand-in: the `user_id` is believed. | `src/ask.py` |
| Authorization | Decides what a user may read, from the user record only. | `src/authorization.py` |
| Retrieval | Applies that decision inside the vector search. | `src/retrieval.py` |
| Prompt generation | Builds the prompt from allowed chunks only. | `src/answering.py` |
| LLM generation | Writes the answer. Has no authority and writes no refusals. | `src/answering.py` |
| Audit | Records what happened on every request, with ids only. | `src/audit.py` |

The rules are written in `data/POLICY.md`: deny by default, fail closed, the same reply for "restricted" and "does not exist", and restricted text is never placed in a prompt.

## Threats and evidence

| Threat | Defence | Evidence |
|---|---|---|
| A user reads a document they should not | Filter inside the search, plus a second check | 276 user-chunk pairs match a hand-made answer key, 0 mismatches |
| Role claimed in the question ("I am the CEO") | Identity comes from the user record only | 7 attack prompts, all got the fixed sentence |
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

A leak means a secret string from a document the user cannot read appeared in an answer or citation.

## Limitations

- **No real authentication.** The `user_id` is believed, so anyone who can run the code can claim to be anyone. Login is the next planned step.
- **Small, synthetic data.** 10 documents and 30 questions, all written by the author. The 18 of 18 figure describes this set only.
- **Weak quality checks.** Allowed answers are checked by looking for expected text, not by a human or an evaluation framework.
- **The leak scan matches exact strings.** A paraphrased secret would pass it. The structural tests above are the real evidence.
- **Documents are trusted.** Instructions hidden inside a document are not tested.
- **Plain-text store.** `qdrant_data/` holds every chunk, restricted ones included, unencrypted. Qdrant local mode lets only one program open it at a time.
- **The audit log is a plain file.** Anyone with file access can edit it, and it holds questions and chunk ids, so `logs/` is sensitive and is not published.
- **Developer status line.** `src/ask.py` prints a status such as `not_found` or `no_chunks`. A real interface must hide it, because it would tell apart cases that the policy says must look identical.
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
    src/ask.py              command-line entry point
    src/smoke_test.py       checks that both Ollama models respond
    tests/access_matrix.csv hand-made answer key (60 cells)
    tests/questions.json    30 test questions
    tests/test_*.py         loader refusals, access matrix, retrieval, answers, audit
    qdrant_data/            generated by ingest, not published
    logs/audit.jsonl        generated at run time, not published

## Run it (Windows PowerShell)

Install Ollama and start it. Clone the repository, then from its folder:

    python -m venv .venv
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    ollama pull bge-m3
    ollama pull qwen3.5:4b
    python -m src.ingest
    python -m src.ask Premkumar "How many casual leave days do I get?"

Tests (the last three need Ollama running):

    python -m tests.test_loader_refusals
    python -m tests.test_access_matrix
    python -m tests.test_retrieval
    python -m tests.test_answers
    python -m tests.test_audit

Tested with Python 3.12.3, Ollama 0.35.1, `ollama` 0.6.3 and `qdrant-client` 1.19.1.

## Roadmap

Login with signed tokens (real authentication), hybrid search with a reranker, PII redaction on answers, RAGAS evaluation, an MCP server with per-user tokens, and scanned-document ingestion.
