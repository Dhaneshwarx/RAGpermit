# Fictional permit practice

These two documents are authored training fixtures, not laws, municipal guidance, actual fees or company policies. Permitville and training credits are invented.

- practice-permit-rules.md: public fee/checklist passages with qualifications and a complete Markdown table.
- practice-review-notes.md: an Engineering clearance-2 passage containing a fake internal review token.

Use the four accounts from ../four-member-team/users.json in a separate workspace. With the optional CEO policy enabled, Dhanesh can read both documents. Arjun can read the Engineering passage; Deepak and Kavin cannot. All four can read the public passage.

Run the isolated model/index checks from the project root:

```powershell
.\.venv\Scripts\python.exe -m tests.test_permit_live
```

The test creates its own temporary workspace and removes it after completing. Follow docs/MANUAL_FINISH.md for persistent practice accounts, passwords and browser use.
