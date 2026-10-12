# THE ISSUER: creates the secret key (once) and signs sign-in tokens.   (data/POLICY.md, section 6)
#
# This is a stand-in for a login page. It does not ask for a password yet, so anybody who can
# run it can get a token for any user in data/users.json. That is the known limit written in
# the policy. Passwords are a later step.
#
# Usage:   python -m src.issue_token <user_id> [seconds]
#          seconds = how long the token lives, 1 to 3600 (default 900, which is 15 minutes)
#
# The token alone goes to standard output, so a shell can capture it. In PowerShell:
#          $env:PERMITRAG_TOKEN = python -m src.issue_token Premkumar
# Messages go to standard error, so they can never end up inside the captured token.

import json
import secrets
import sys
import time
from pathlib import Path

import src.authentication as authentication
from src.authorization import load_users

DEFAULT_LIFETIME_SECONDS = 900


def create_key_if_missing(key_path=None):
    # Returns True if a new key was created, False if a usable key was already there.
    # An existing file is NEVER overwritten: replacing the key revokes every token (policy),
    # and the file could be a key that somebody placed by hand.
    if key_path is None:
        key_path = authentication.KEY_PATH
    path = Path(key_path)
    if authentication.load_key(path) is not None:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "xb") as file:  # "x" = create the file, and fail if it already exists
            file.write(secrets.token_hex(32).encode("ascii"))  # 64 random hex characters
    except FileExistsError:
        raise RuntimeError(
            str(path) + " exists but is not a usable key (it needs at least 32 bytes). "
            "Fix or delete that file, then try again."
        )
    try:
        path.chmod(0o600)  # owner only. Best effort: Windows ignores most of this.
    except OSError:
        pass
    return True


def issue_token(user_id, lifetime=DEFAULT_LIFETIME_SECONDS, now=None, key_path=None):
    # Returns the token as text. Raises ValueError if the request would break a rule of section 6.
    if not isinstance(user_id, str) or user_id == "":
        raise ValueError("user_id must be a non-empty piece of text")
    if type(lifetime) is not int or not 1 <= lifetime <= authentication.MAX_LIFETIME_SECONDS:
        raise ValueError("seconds must be a whole number from 1 to " + str(authentication.MAX_LIFETIME_SECONDS))
    if now is None:
        now = int(time.time())
    if key_path is None:
        key_path = authentication.KEY_PATH

    create_key_if_missing(key_path)
    key = authentication.load_key(key_path)
    if key is None:
        raise RuntimeError("the key could not be read from " + str(key_path))

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "iat": now, "exp": now + lifetime}
    signing_text = (
        authentication.encode_part(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + authentication.encode_part(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    token = signing_text + "." + authentication.sign(signing_text, key)

    # Never hand out a token that the checker would refuse (for example one that is too long).
    _, reason = authentication.check_token(token, key, now)
    if reason is not None:
        raise ValueError("this token would not pass the checker (" + reason + ")")
    return token


def main():
    arguments = sys.argv[1:]
    if len(arguments) not in (1, 2):
        print("Usage: python -m src.issue_token <user_id> [seconds]", file=sys.stderr)
        return 2
    user_id = arguments[0]

    lifetime = DEFAULT_LIFETIME_SECONDS
    if len(arguments) == 2:
        if not (arguments[1].isascii() and arguments[1].isdigit()):
            print("seconds must be a whole number from 1 to " + str(authentication.MAX_LIFETIME_SECONDS), file=sys.stderr)
            return 2
        lifetime = int(arguments[1])

    # A typo should fail here with a clear message, not later with a confusing refusal.
    users, _ = load_users()
    if user_id not in users:
        print("Unknown user_id " + repr(user_id) + ". Known users: " + ", ".join(sorted(users)), file=sys.stderr)
        return 1

    try:
        if create_key_if_missing():
            print("Created a new secret key in " + str(authentication.KEY_PATH) + " (never commit it).", file=sys.stderr)
        token = issue_token(user_id, lifetime)
    except (ValueError, RuntimeError, OSError) as error:
        print("No token issued: " + str(error), file=sys.stderr)
        return 1

    print("Token for " + user_id + ", valid for " + str(lifetime) + " seconds.", file=sys.stderr)
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
