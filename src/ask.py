# The command-line front door. The order matters (POLICY.md sections 6, 3 and 4):
#   1. AUTHENTICATION  who is asking? Only a valid signed token counts. Nothing else runs until it passes.
#   2. USER RECORD     department, role and clearance come from data/users.json, never from the token.
#   3. THE REST        authorization, retrieval, prompt, model and audit log: src/answering.py
#
# Usage:    python -m src.ask "<question>"
# Sign in first. In PowerShell:    $env:PERMITRAG_TOKEN = python -m src.issue_token <user_id>
# Sign out:                        Remove-Item Env:PERMITRAG_TOKEN

import os
import sys

import src.authentication as authentication
from src.answering import answer_question, REFUSAL
from src.audit import log_auth_failure, write_audit_entry
from src.authorization import load_users
from src.vector_store import open_store

TOKEN_VARIABLE = "PERMITRAG_TOKEN"


def refuse_sign_in(reason):
    # The same sentence for every failure: it must not tell an attacker which check failed.
    # The reason code goes to the audit log only.
    print(authentication.AUTH_FAILED_MESSAGE)
    try:
        log_auth_failure(reason)
    except Exception:
        pass
    return 1


def main():
    if len(sys.argv) != 2:
        print('Usage: python -m src.ask "<question>"')
        print("Sign in first. In PowerShell:  $env:PERMITRAG_TOKEN = python -m src.issue_token <user_id>")
        return 2
    question = sys.argv[1]

    # 1. AUTHENTICATION. KEY_PATH is read here (not used as a default argument) so that the
    #    tests can point it at a temporary key.
    token = os.environ.get(TOKEN_VARIABLE)
    user_id, reason = authentication.authenticate(token, key_path=authentication.KEY_PATH)
    if reason is not None:
        return refuse_sign_in(reason)

    # 2. The user record. A valid token for a name with no record gives None, and None gets nothing.
    try:
        users, rejected = load_users()
        if rejected:
            raise ValueError("Invalid user records")
        user = users.get(user_id)
        client = open_store()
        try:
            result = answer_question(client, user, question, user_id=user_id)
        finally:
            client.close()
    except Exception:
        try:
            write_audit_entry({"user_id": user_id, "status": "error", "question": question[:500]})
        except Exception:
            pass
        print(REFUSAL)
        return 1

    print(result["answer"])
    if result["sources"]:
        print("Sources:", "; ".join(result["sources"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
