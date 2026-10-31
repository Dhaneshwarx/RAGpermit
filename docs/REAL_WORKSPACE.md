# Private workspace setup

Set `PERMITRAG_WORKSPACE` to an absolute private folder to separate real user records, documents, passwords, signing keys, logs and Qdrant storage from the sample repository. With the variable unset, the sample workspace remains selected.

Create an empty workspace using a new folder path you can write to:

```powershell
python -m src.init_workspace C:\PermitRAGPrivate
$env:PERMITRAG_WORKSPACE = 'C:\PermitRAGPrivate'
```

The command refuses existing folders and creates no demo accounts or documents. Set the variable in every terminal before running PermitRAG commands, and restart existing processes after changing it. The private folder includes a Git ignore file; operating-system permissions are still needed to protect it.

Before ingestion, configure real user records in `data/users.json` and permission-tagged Markdown documents in `data/docs/` inside that folder. The current department and role vocabulary is defined in `src/policy_values.py`; it must match the intended organization's policy. PDF/Word uploads, administrator management screens and public hosting are not yet implemented.

Run sample regression tests with `PERMITRAG_WORKSPACE` unset. They intentionally use the fictional dataset and must not run against private organization data.

This is the first step toward real operation, not a production-readiness claim. The deployment environment, organization access policy and required document formats must be specified before completing that setup.
