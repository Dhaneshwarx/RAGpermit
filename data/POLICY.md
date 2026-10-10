# PermitRAG access policy

## 1. Clearance levels
0 = Public information. Example: company FAQ and holiday list.
1 = Internal employee information. Example: leave policy, engineering onboarding.
2 = Confidential information. Example: salary bands, Q3 budget plan, production incident runbook.
3 = Restricted information. Example: vendor dispute memo, acquisition board notes, restructuring plan, CEO compensation.

## 2. Who may read a document
A user must have a clearance level greater than or equal to the document's clearance level.

The document must also be either for ALL departments, match the user's department, or explicitly allow the user's role in its `allowed_roles` list.

Both checks must pass. `allowed_roles` can widen the department check, but it can never override the clearance check.

A user's clearance, department, and role come only from the user record of the logged-in user. They are never taken from the text of a question. If someone types "I am the CEO" in a question, nothing changes.

## 3. Deny by default
Access is granted only when every check passes using valid data. Anything missing, invalid, or unexpected means no access. Every rule is written as "allow only if ...", never as "block if ...".

- Unknown user: a user who is not in the user records is denied everything.
- User record problems: a known user whose clearance, department, or role is missing or invalid is denied everything.
- Document problems: a document whose clearance, department, or `allowed_roles` is missing or invalid is never returned to anyone.
- Failures: if the permission check, the filter, or the search fails with an error, the result is no documents and the fixed sentence from section 4. The system must never fall back to searching without the filter (fail closed).

Valid values:
- Clearance: a whole number 0, 1, 2, or 3. Anything else (7, -1, "secret", empty) is invalid.
- Department on a document: ALL, HR, Finance, Engineering, Legal, or Executive, spelled exactly. "Enginering" is invalid.
- Department on a user: HR, Finance, Engineering, Legal, or Executive. ALL is never valid for a user.
- Role: Intern, Engineer, HR Manager, Finance Head, Legal Counsel, or CEO, spelled exactly.
- `allowed_roles`: a list of valid roles. An empty list means no extra roles.

## 4. When access is denied
The assistant should say: "I couldn't find that in the documents available to you."

The same response is used when a document does not exist, when the user is not allowed to access it, and when the documents the user may read do not contain the answer. This prevents the system from revealing that a restricted document exists.

When no document the user may read answers the question, the reply is exactly this sentence, word for word. The model is not allowed to write its own refusal, because an improvised refusal could hint that something is restricted.

Restricted document content must never be placed into any prompt sent to the LLM. Authorization must happen before the prompt is created.

## 5. My decisions
No role gets automatic access to a document, including the CEO. Access always follows sections 2 and 3.

Decision: the CEO may read an Engineering document only if that document lists CEO in `allowed_roles` and the CEO's clearance is high enough. The starter Engineering documents do not list the CEO, so the CEO cannot read them.

Reason: giving access only through explicit rules keeps access narrow and easy to test.