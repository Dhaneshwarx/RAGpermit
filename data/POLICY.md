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

## 6. Who is asking (authentication)

Sections 1 to 5 decide what a user may read. This section decides who the user is. It runs first, and nothing else runs until it succeeds.

Identity comes only from a valid sign-in token. A name typed on the command line, a name written inside a question, and a name inside a token that failed any check below are never used as identity.

A token has three parts joined by dots: a header, a payload and a signature. The signature is made with a secret key that only this system holds, so nobody can change a token or make a new one without that key.

The payload carries identity and timing only:
- sub: the user_id of the person.
- iat: when the token was issued, in whole seconds since 1 January 1970 UTC.
- exp: when the token stops being valid, in the same unit.

The payload never carries clearance, department or role. Those still come only from the user record on every request, so changing or removing a user takes effect at once. Any extra claim in a payload is ignored.

A token is valid only if every one of these checks passes:
- It has exactly three parts separated by dots, and none is empty.
- Each part is valid base64url text, and the header and payload decode to JSON objects.
- The header's alg is exactly "HS256". Any other value, including "none", is invalid.
- The signature matches the header and payload under the current key. The comparison is constant-time, so response time does not reveal how much of a guess was right.
- sub is a non-empty piece of text.
- iat and exp are whole numbers. true, false, decimals and text are invalid.
- iat is not in the future, and the current time is before exp. A token is no longer valid at the moment exp is reached.
- exp minus iat is at most 3600 seconds (1 hour). A token's own claim about how long it should live is not trusted beyond that.

Anything else means no sign-in. Like section 3, every rule is "allow only if".

The key:
- It lives in keys/token_key.txt, which is listed in .gitignore and never committed.
- It must be at least 32 bytes. A missing, empty or shorter key means no token is valid (fail closed). The checker never creates a key. Only the issuer does.
- Replacing the key makes every existing token invalid. That is how all tokens are revoked at once. There is no per-token revocation list. Tokens are short-lived instead.

When sign-in fails:
- The reply is always: "Authentication failed. Please sign in." The same sentence is used for a missing token, a garbled token, a changed token, a wrong key, an expired token and a missing key. It must not say which check failed, because that would tell an attacker what to fix.
- No embedding, search or model call happens.
- The audit log records the status auth_failed and a short reason code. It never records the token, and never records a name taken from a token that did not pass every check.

When sign-in succeeds, the sub value goes to the user lookup like any other user_id. A valid token for a name that is not in the user records is an unknown user (section 3): denied everything, with the fixed sentence from section 4.

Decision: tokens are made and checked with Python's standard library (HMAC-SHA256), in plain code, so every rule above is a visible line.
Reason: this project is for learning, and a visible check is easier to test.
Limit: until passwords are added, anyone who can run the issuer can get a token for any user. Production would use a vetted library, public-key signatures and single sign-on.

Details that keep these rules exact:
- Token text uses only the letters A to Z and a to z, the digits 0 to 9, the minus sign and the underscore, plus the two dots between parts. There is no = padding, and there are no spaces or line breaks anywhere. The checker does not trim a token. Anything else is malformed.
- A token longer than 2048 characters is malformed.
- The signature covers the first two parts exactly as written in the token, joined by a dot. It must be exactly the text the issuer would produce, so changing any single character of a token makes it invalid, even a character that would decode to the same bytes.
- Header fields other than alg are ignored.
- A number written with a decimal point or an exponent, such as 5.0 or 1e3, is not a whole number, even when its value is whole.
- No token means nothing was supplied, or an empty string was supplied. A token made only of spaces is malformed.
- The key is the content of the key file with spaces, tabs and line breaks removed from both ends. The 32-byte minimum is counted after that removal.
- The sub value is used exactly as written. It is not trimmed and its letters are not changed to upper or lower case.
- There is no allowance for clock differences, because the issuer and the checker run on the same machine.
- No claim from the payload is used until the signature has passed.
- Checks run in this order: no token, then the key, then the validity checks listed above, from top to bottom. The audit reason names the first check that fails: no_token, no_key, malformed (the first two validity checks, the character rule or the length limit), bad_alg, bad_signature, bad_claims (the sub check and the whole-number check), not_yet_valid (iat in the future), expired (exp reached) or lifetime_too_long.
