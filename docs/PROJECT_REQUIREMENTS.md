# PermitRAG completion requirements

## Stage A: local operation

- [x] Browser password login, questions, citations and sign-out implemented.
- [x] Private workspace configuration and empty-workspace initializer implemented.
- [x] Proposed team and eight permission-tagged documents prepared in examples/company-starter.
- [ ] Owner approves real user identities, document content and access matrix.
- [ ] Admin can add/disable users and reset passwords without editing JSON manually.
- [ ] Admin can import, update and delete text documents with explicit permissions.
- [ ] Ingestion handles rejected/empty documents without a traceback.
- [ ] Document updates and deletions cannot leave stale permissions searchable.
- [ ] Long documents are split into bounded chunks; broad questions and summaries are evaluated.
- [ ] Conversations support follow-up questions without crossing user permissions.
- [ ] Sessions can be revoked; logout and password reset invalidate intended sessions.
- [ ] Administrator diagnostics distinguish unavailable models from missing answers.
- [ ] Backup and restore are documented and tested.
- [ ] Real-content evaluation checks factual answers, citations, refusals and response time.

Stage A acceptance: a fresh private workspace can be set up, users can be managed, documents can be maintained, and authorized/denied question tests pass through the browser. Current code is still in progress.

## Stage B: company network

- [ ] Select the host computer, intended users and concurrent request target.
- [ ] Replace the development HTTP server with a supported deployment server.
- [ ] Configure HTTPS, host/origin allowlists and appropriate cookies.
- [ ] Use storage and request handling appropriate for concurrent access.
- [ ] Apply per-user rate limits, session controls and access-change tests.
- [ ] Test from a second computer, including recovery after restart.

Do not achieve Stage B by only changing the bind address to 0.0.0.0.

## Stage C: remote hosting

- [ ] Choose hosting, domain, budget, model hosting and data residency.
- [ ] Configure HTTPS, production identity and account recovery.
- [ ] Configure secrets, backups, monitoring, updates and incident procedures.
- [ ] Test authorization, uploads, session handling and restoration in the deployed environment.
- [ ] Verify external access and operational ownership before launch.

## Dependencies

Python dependencies remain in the existing requirements.txt. No new Python dependency is needed for this starter pack. Ollama requires bge-m3 and qwen3.5:4b. PDF and Word ingestion are outside the current text-first scope.

## Data rules

The starter pack is synthetic and must not be presented as actual company records. Private company documents, users, passwords, keys and logs stay outside the public repository. Adding a role name to allowed_roles deliberately grants cross-department access, subject to clearance; CEO does not automatically bypass the policy.
