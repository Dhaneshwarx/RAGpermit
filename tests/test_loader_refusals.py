import tempfile
from pathlib import Path

from src.document_loader import load_all_documents

# Every test document is written out in full, so you can see what is wrong with it.
# The lines inside the triple quotes start at the left edge on purpose: they are the
# file's text, and any spaces here would become part of the document.
DOCUMENTS = {
    "valid-control.md": """---
doc_id: valid-control
title: Control
department: HR
clearance: 1
allowed_roles: []
---
Text before a horizontal rule.
---
Text after the horizontal rule.
""",
    "unclosed-header.md": """---
doc_id: unclosed-header
title: Test
department: HR
clearance: 1
allowed_roles: []

The header above is never closed.
""",
    "line-without-colon.md": """---
doc_id: line-without-colon
title: Test
department HR
clearance: 1
allowed_roles: []
---
Body.
""",
    "missing-clearance.md": """---
doc_id: missing-clearance
title: Test
department: HR
allowed_roles: []
---
Body.
""",
    "clearance-with-zero.md": """---
doc_id: clearance-with-zero
title: Test
department: HR
clearance: 02
allowed_roles: []
---
Body.
""",
    "roles-without-brackets.md": """---
doc_id: roles-without-brackets
title: Test
department: HR
clearance: 1
allowed_roles: CEO
---
Body.
""",
    "wrong-doc-id.md": """---
doc_id: some-other-name
title: Test
department: HR
clearance: 1
allowed_roles: []
---
Body.
""",
}

with tempfile.TemporaryDirectory() as folder_name:
    folder = Path(folder_name)
    for file_name, text in DOCUMENTS.items():
        (folder / file_name).write_text(text, encoding="utf-8")

    accepted, rejected = load_all_documents(folder)

print("Accepted:", [document["header"]["doc_id"] for document in accepted])
for file_name, reason in rejected:
    print("Rejected:", file_name, "->", reason)

# assert stops the program with an error if the condition is False.
assert [document["header"]["doc_id"] for document in accepted] == ["valid-control"]
assert "Text after the horizontal rule." in accepted[0]["body"]
assert len(rejected) == 6
print("All refusal checks passed.")