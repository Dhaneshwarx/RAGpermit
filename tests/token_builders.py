# Builds the sign-in tokens used by the tests.
#
# This file does NOT import src/authentication.py. It has its own small base64url, JSON and
# HMAC code. If the tests built their tokens with the checker's own functions, a mistake in
# those functions would be copied into every token and the tests would never notice it.
#
# The clock is frozen: NOW is the "current time" of every test that uses it.

import base64
import hashlib
import hmac
import json

NOW = 1_700_000_000                     # 14 November 2023, 22:13:20 UTC
GOOD_KEY = b"0123456789abcdef" * 4      # 64 bytes: the key most tokens are signed with
OTHER_KEY = b"fedcba9876543210" * 4     # a different key
KEY_31 = GOOD_KEY[:31]                  # one byte too short
KEY_32 = GOOD_KEY[:32]                  # exactly long enough
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def b64(raw_bytes):
    # bytes -> base64url text without the "=" padding
    return base64.urlsafe_b64encode(raw_bytes).decode("ascii").rstrip("=")


def unb64(text):
    # base64url text (without padding) -> bytes
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def to_json(value):
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def payload_dict(sub="Srikanth", iat=NOW, exp=None, **extra):
    # A normal payload: issued at NOW, valid for 15 minutes. Extra claims can be added.
    payload = {"sub": sub, "iat": iat, "exp": NOW + 900 if exp is None else exp}
    payload.update(extra)
    return payload


def make_token(header=None, payload=None, key=GOOD_KEY, digest=hashlib.sha256,
               header_bytes=None, payload_bytes=None):
    # header and payload are dicts that get written out as JSON.
    # header_bytes and payload_bytes are raw bytes, for tokens whose contents are deliberately wrong.
    if header_bytes is None:
        header_bytes = to_json({"alg": "HS256", "typ": "JWT"} if header is None else header)
    if payload_bytes is None:
        payload_bytes = to_json(payload_dict() if payload is None else payload)
    header_text = b64(header_bytes)
    payload_text = b64(payload_bytes)
    signing_text = header_text + "." + payload_text
    signature = b64(hmac.new(key, signing_text.encode("ascii"), digest).digest())
    return signing_text + "." + signature


def token_of_length(total):
    # A correctly signed token of EXACTLY `total` characters: a long "pad" claim fills it up.
    for number in range(3000):
        token = make_token(payload=payload_dict("Dhanesh", pad="x" * number))
        if len(token) == total:
            return token
        if len(token) > total:
            break
    raise ValueError("cannot build a token of " + str(total) + " characters")


def same_bytes_last_char(token):
    # Changes the LAST character of the signature to a different character that decodes to the
    # SAME bytes. (The last character carries unused bits, so several characters share one value.)
    header_text, payload_text, signature = token.split(".")
    wanted = unb64(signature)
    for character in ALPHABET:
        if character != signature[-1] and unb64(signature[:-1] + character) == wanted:
            return header_text + "." + payload_text + "." + signature[:-1] + character
    raise ValueError("no look-alike character found")


def standard_alphabet_variant():
    # A valid token whose signature contains "-" or "_", with that character swapped for the
    # standard-base64 "+" or "/". Only some signatures contain "-" or "_", so we search for one.
    for extra_seconds in range(5000):
        token = make_token(payload=payload_dict(exp=NOW + 900 + extra_seconds))
        header_text, payload_text, signature = token.split(".")
        for position, character in enumerate(signature):
            if character in "-_":
                swapped = "+" if character == "-" else "/"
                changed = signature[:position] + swapped + signature[position + 1:]
                return header_text + "." + payload_text + "." + changed
    raise ValueError("no suitable signature found")


def other_letter(character):
    return "B" if character != "B" else "C"


def build_cases():
    # {case_id: (token, key_file_bytes)} for every row of tests/token_cases.csv.
    # key_file_bytes is what the key file contains, or None when there is no key file at all.
    good = make_token()
    good_header, good_payload, good_signature = good.split(".")
    key_file = GOOD_KEY + b"\n"

    return {
        # Valid tokens
        "ok-01": (make_token(payload=payload_dict("Srikanth")), key_file),
        "ok-02": (make_token(payload=payload_dict("Deepak", iat=NOW - 100, exp=NOW + 1)), key_file),
        "ok-03": (make_token(payload=payload_dict("Yash", exp=NOW + 3600)), key_file),
        "ok-04": (make_token(payload=payload_dict("Premkumar", role="CEO", clearance=3)), key_file),
        "ok-05": (make_token(header={"alg": "HS256", "kid": "anything"}, payload=payload_dict("Mahasri")), key_file),
        "ok-06": (make_token(payload=payload_dict("dhanesh")), key_file),
        "ok-07": (token_of_length(2048), key_file),
        # No token
        "none-01": (None, key_file),
        "none-02": ("", key_file),
        "none-03": (None, None),
        # Malformed
        "shape-01": ("   ", key_file),
        "shape-02": (good_header + "." + good_payload, key_file),
        "shape-03": (good + ".extra", key_file),
        "shape-04": (b64(to_json({"alg": "none", "typ": "JWT"})) + "." + good_payload + ".", key_file),
        "shape-05": (good_header[:18] + "*" + good_header[18:] + "." + good_payload + "." + good_signature, key_file),
        "shape-06": (good_header[:18] + " " + good_header[18:] + "." + good_payload + "." + good_signature, key_file),
        "shape-07": (standard_alphabet_variant(), key_file),
        "shape-08": (good_header + "." + good_payload + "=." + good_signature, key_file),
        "shape-09": (good_header + "." + good_payload + "." + good_signature[:20] + chr(233) + good_signature[20:], key_file),
        "shape-10": (" " + good, key_file),
        "shape-11": (good + "\n", key_file),
        "shape-12": (good_header + "\n." + good_payload + "." + good_signature, key_file),
        "shape-13": (good_header + ".abcde." + good_signature, key_file),
        "shape-14": (make_token(payload_bytes=b"not json"), key_file),
        "shape-15": (make_token(payload_bytes=b"\xff\xfe"), key_file),
        "shape-16": (make_token(payload_bytes=b'["Dhanesh"]'), key_file),
        "shape-17": (make_token(header_bytes=b'"HS256"'), key_file),
        "shape-18": (token_of_length(2049), key_file),
        # Wrong algorithm
        "alg-01": (make_token(header={"alg": "none", "typ": "JWT"}), key_file),
        "alg-02": (make_token(header={"alg": "HS512", "typ": "JWT"}, digest=hashlib.sha512), key_file),
        "alg-03": (make_token(header={"alg": "hs256", "typ": "JWT"}), key_file),
        "alg-04": (make_token(header={"typ": "JWT"}), key_file),
        # Wrong signature
        "sig-01": (good_header + "." + b64(to_json(payload_dict("Dhanesh"))) + "." + make_token(payload=payload_dict("Premkumar")).split(".")[2], key_file),
        "sig-02": (make_token(key=OTHER_KEY), key_file),
        "sig-03": (b64(to_json({"alg": "HS256", "typ": "JWT", "kid": "1"})) + "." + good_payload + "." + good_signature, key_file),
        "sig-04": (good_header + "." + good_payload + "." + other_letter(good_signature[0]) + good_signature[1:], key_file),
        "sig-05": (same_bytes_last_char(good), key_file),
        "sig-06": (good_header + "." + b64(to_json({"iat": NOW, "exp": NOW + 900})) + "." + good_signature, key_file),
        # Bad claims
        "claims-01": (make_token(payload={"iat": NOW, "exp": NOW + 900}), key_file),
        "claims-02": (make_token(payload=payload_dict("")), key_file),
        "claims-03": (make_token(payload=payload_dict(None)), key_file),
        "claims-04": (make_token(payload=payload_dict(42)), key_file),
        "claims-05": (make_token(payload=payload_dict(iat=True)), key_file),
        "claims-06": (make_token(payload=payload_dict(exp=NOW + 900.0)), key_file),
        "claims-07": (make_token(payload_bytes=b'{"sub":"Srikanth","iat":1700000000,"exp":1.7000009e9}'), key_file),
        "claims-08": (make_token(payload=payload_dict(iat="1700000000")), key_file),
        "claims-09": (make_token(payload={"sub": "Srikanth", "iat": NOW}), key_file),
        # Time
        "time-01": (make_token(payload=payload_dict(iat=NOW + 1, exp=NOW + 901)), key_file),
        "time-02": (make_token(payload=payload_dict(iat=NOW - 100, exp=NOW)), key_file),
        "time-03": (make_token(payload=payload_dict(iat=NOW - 100, exp=NOW - 1)), key_file),
        "time-04": (make_token(payload=payload_dict(iat=NOW - 315_360_000, exp=NOW - 86_400)), key_file),
        "life-01": (make_token(payload=payload_dict(iat=NOW - 1800, exp=NOW + 1801)), key_file),
        "life-02": (make_token(payload=payload_dict(iat=NOW, exp=NOW + 315_360_000)), key_file),
        # The key file
        "key-01": (good, None),
        "key-02": (good, b""),
        "key-03": (good, b" " * 40 + b"\n"),
        "key-04": (make_token(key=KEY_31), KEY_31),
        "key-05": (make_token(key=KEY_31), KEY_31 + b"\n"),
        "key-06": (make_token(key=KEY_32), KEY_32),
        "key-07": (make_token(key=KEY_32), b"  " + KEY_32 + b"\t\r\n"),
        "key-08": ("garbage", None),
    }
