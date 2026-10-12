# AUTHENTICATION: who is asking?   (data/POLICY.md, section 6)
#
# This file answers one question: "is this sign-in token genuine, and whose is it?"
# It never decides what anybody may read. That is authorization.py.
# It never creates a key either: only the issuer (issue_token.py) does.
#
# The answer is always a pair:
#     (user_id, None)   the token is valid and belongs to user_id
#     (None, reason)    the token is not valid; reason is a short code for the audit log
# Reason codes: no_token, no_key, malformed, bad_alg, bad_signature,
#               bad_claims, not_yet_valid, expired, lifetime_too_long

import base64
import hashlib
import hmac
import json
import re
import time
from pathlib import Path

KEY_PATH = Path("keys/token_key.txt")
MIN_KEY_BYTES = 32            # a shorter key means that no token is valid
MAX_TOKEN_LENGTH = 2048       # a longer token is malformed
MAX_LIFETIME_SECONDS = 3600   # exp minus iat may not be more than one hour

# The one sentence a person sees for EVERY kind of failed sign-in (section 6).
AUTH_FAILED_MESSAGE = "Authentication failed. Please sign in."

# A token part may use only these characters: A-Z a-z 0-9 - _
# Python's own decoder is more relaxed: it silently skips characters such as * and spaces,
# so we check the characters ourselves. fullmatch demands that the WHOLE part fits the
# pattern, so not even a line break at the end can slip through.
PART_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def encode_part(raw_bytes):
    # bytes -> base64url text, without the "=" padding
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def decode_part(text):
    # base64url text -> bytes. The padding that tokens leave out is added back here.
    # Raises ValueError when the text cannot be decoded.
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign(signing_text, key):
    # HMAC-SHA256 of "header.payload", written as base64url text.
    digest = hmac.new(key, signing_text.encode("ascii"), hashlib.sha256).digest()
    return encode_part(digest)


def load_key(key_path=KEY_PATH):
    # Returns the key as bytes, or None when there is no usable key. Never creates a key.
    # The file is read as bytes, so no text decoding can fail. Spaces, tabs and line breaks
    # are removed from both ends, and the 32-byte minimum is counted AFTER that.
    try:
        raw = Path(key_path).read_bytes()
    except OSError:
        return None
    key = raw.strip(b" \t\r\n")
    if len(key) < MIN_KEY_BYTES:
        return None
    return key


def check_token(token, key, now):
    # The eight checks of section 6, in the order written there. The first one that fails
    # decides the reason. `now` is a whole number of seconds since 1 January 1970 UTC.
    # It is a parameter (not read here) so that tests can freeze the clock.
    if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:
        return None, "malformed"

    # Check 1: exactly three parts separated by dots, and none of them empty.
    parts = token.split(".")
    if len(parts) != 3 or "" in parts:
        return None, "malformed"

    # Check 2 (a): only the allowed characters. No spaces, no line breaks, no "=" padding.
    for part in parts:
        if PART_PATTERN.fullmatch(part) is None:
            return None, "malformed"

    # Check 2 (b): every part decodes, and the header and the payload are JSON objects.
    # ValueError covers bad base64, bad text and bad JSON. RecursionError covers JSON
    # nested so deeply that Python gives up (the length limit above already stops that).
    try:
        header = json.loads(decode_part(parts[0]).decode("utf-8"))
        payload = json.loads(decode_part(parts[1]).decode("utf-8"))
        decode_part(parts[2])
    except (ValueError, RecursionError):
        return None, "malformed"
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return None, "malformed"

    # Check 3: the algorithm is exactly HS256. The header never gets to choose how we
    # check a token: "none", "HS512", "hs256" and a missing alg are all refused.
    if header.get("alg") != "HS256":
        return None, "bad_alg"

    # Check 4: the signature matches. The signature covers the first two parts exactly as
    # they were written. We compare TEXT, not decoded bytes: several different-looking
    # texts can decode to the same bytes, and only the issuer's own text is accepted.
    # compare_digest takes the same time however many characters match.
    expected = sign(parts[0] + "." + parts[1], key)
    if not hmac.compare_digest(parts[2], expected):
        return None, "bad_signature"

    # From here on the payload is genuine: it was signed with our key. Not before.

    # Check 5: sub is a non-empty piece of text. It is used exactly as written.
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or user_id == "":
        return None, "bad_claims"

    # Check 6: iat and exp are whole numbers. "type(x) is int" is stricter than isinstance:
    # in Python, True counts as 1, and 5.0 equals 5, but neither is a whole number here.
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    if type(issued_at) is not int or type(expires_at) is not int:
        return None, "bad_claims"

    # Check 7: not issued in the future, and not expired. At the moment exp is reached
    # the token is already over.
    if issued_at > now:
        return None, "not_yet_valid"
    if now >= expires_at:
        return None, "expired"

    # Check 8: the token's own life (exp minus iat) is at most one hour.
    if expires_at - issued_at > MAX_LIFETIME_SECONDS:
        return None, "lifetime_too_long"

    return user_id, None


def authenticate(token, now=None, key_path=KEY_PATH):
    # The one function the rest of the system calls.
    # Order (section 6): no token, then the key, then the eight checks.
    if token is None or token == "":
        return None, "no_token"

    key = load_key(key_path)
    if key is None:
        return None, "no_key"

    if now is None:
        now = int(time.time())
    return check_token(token, key, now)
