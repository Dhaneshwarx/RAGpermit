# Break-the-checker test: proves that tests/test_auth.py can really FAIL.
#
# A test that has never failed might be testing nothing. So this file makes copies of
# src/authentication.py, each with ONE planted mistake of the kind programmers really make
# (forgetting to check the algorithm, using > where >= belongs, and so on), and runs the same
# checks against every copy. A copy that passes all the checks would mean a hole in the tests.
#
# Each mistake is a list of (exact old text, new text). The old text must occur exactly once
# in src/authentication.py. If you change that file, this test will tell you which line moved.
#
# Run:  python -m tests.test_auth_breaks

import importlib.util
import tempfile
from pathlib import Path

import src.authentication as authentication
from tests.test_auth import find_problems

SOURCE_FILE = Path("src/authentication.py")

LENGTH_LINE = "if not isinstance(token, str) or len(token) > MAX_TOKEN_LENGTH:"
PARTS_LINE = 'if len(parts) != 3 or "" in parts:'
SPLIT_LINE = 'parts = token.split(".")'
PATTERN_LINE = 'PART_PATTERN = re.compile(r"[A-Za-z0-9_-]+")'
JSON_LINE = "except (ValueError, RecursionError):"
ALG_LINE = 'if header.get("alg") != "HS256":'
SIGNATURE_LINE = "if not hmac.compare_digest(parts[2], expected):"
SIGNING_LINE = 'expected = sign(parts[0] + "." + parts[1], key)'
SUB_LINE = 'user_id = payload.get("sub")'
SUB_CHECK_LINE = 'if not isinstance(user_id, str) or user_id == "":'
NUMBER_LINE = "if type(issued_at) is not int or type(expires_at) is not int:"
LIFE_LINE = "if expires_at - issued_at > MAX_LIFETIME_SECONDS:"
KEY_FILE_LINE = "except OSError:\n        return None"
TOKEN_LINE = 'if token is None or token == "":'

MISTAKES = [
    # Length and shape
    ("no limit on the token length", [(" or len(token) > MAX_TOKEN_LENGTH:", ":")]),
    ("a 2048-character token is refused", [("len(token) > MAX_TOKEN_LENGTH", "len(token) >= MAX_TOKEN_LENGTH")]),
    ("a 2049-character token is accepted", [("len(token) > MAX_TOKEN_LENGTH", "len(token) > MAX_TOKEN_LENGTH + 1")]),
    ("something that is not text crashes", [(LENGTH_LINE, "if len(token) > MAX_TOKEN_LENGTH:")]),
    ("four parts are accepted", [(PARTS_LINE, 'if len(parts) < 3 or "" in parts:')]),
    ("two parts crash the checker", [(PARTS_LINE, 'if len(parts) > 3 or "" in parts:')]),
    ("an empty part is accepted", [(PARTS_LINE, "if len(parts) != 3:"),
                                   (PATTERN_LINE, 'PART_PATTERN = re.compile(r"[A-Za-z0-9_-]*")')]),
    ("the token is trimmed on both sides", [(SPLIT_LINE, 'parts = token.strip().split(".")')]),
    ("the token is trimmed on the right", [(SPLIT_LINE, 'parts = token.rstrip().split(".")')]),
    ("the characters are not checked", [("if PART_PATTERN.fullmatch(part) is None:", "if False:")]),
    ("only the start of a part is checked", [("PART_PATTERN.fullmatch(part)", "PART_PATTERN.match(part)")]),
    ("standard base64 symbols (+ / =) are allowed", [(PATTERN_LINE, 'PART_PATTERN = re.compile(r"[A-Za-z0-9_+/=-]+")')]),
    ("signatures keep their = padding", [('.decode("ascii").rstrip("=")', '.decode("ascii")')]),
    ("padding is not added back before decoding", [('padding = "=" * (-len(text) % 4)', 'padding = ""')]),
    # Decoding and JSON
    ("bad JSON is not caught", [(JSON_LINE, "except ():")]),
    ("too-deep JSON is not caught", [(JSON_LINE, "except ValueError:")]),
    ("the header may be any kind of JSON", [("not isinstance(header, dict) or ", "")]),
    ("the payload may be any kind of JSON", [(" or not isinstance(payload, dict)", "")]),
    # Algorithm
    ("the algorithm is not checked", [(ALG_LINE, "if False:")]),
    ("the algorithm is compared in capital letters", [(ALG_LINE, 'if str(header.get("alg")).upper() != "HS256":')]),
    ("a missing algorithm crashes", [(ALG_LINE, 'if header["alg"] != "HS256":')]),
    ('alg "none" is accepted without a signature', [(ALG_LINE, 'if header.get("alg") == "none":\n        return payload.get("sub"), None\n    ' + ALG_LINE)]),
    ("extra header fields are refused", [(ALG_LINE, 'if set(header) - {"alg", "typ"} or header.get("alg") != "HS256":')]),
    # Signature
    ("the signature is not checked", [(SIGNATURE_LINE, "if False:")]),
    ("signatures are compared as decoded bytes", [(SIGNATURE_LINE, "if not hmac.compare_digest(decode_part(parts[2]), decode_part(expected)):")]),
    ("the signature is compared with == (not constant-time)", [("hmac.compare_digest(parts[2], expected)", "parts[2] == expected")]),
    ("the signed text is rebuilt from the decoded parts", [(SIGNING_LINE, 'expected = sign(encode_part(decode_part(parts[0])) + "." + encode_part(decode_part(parts[1])), key)')]),
    ("the signature uses SHA-512", [("hashlib.sha256", "hashlib.sha512")]),
    ("the claims are read before the signature is checked", [(SIGNING_LINE, 'if not isinstance(payload.get("sub"), str):\n        return None, "bad_claims"\n    ' + SIGNING_LINE)]),
    # Claims
    ("extra payload claims are refused", [(SUB_LINE, 'if set(payload) != {"sub", "iat", "exp"}:\n        return None, "bad_claims"\n    ' + SUB_LINE)]),
    ("an empty sub is accepted", [(' or user_id == ""', "")]),
    ("a sub that is not text is accepted", [(SUB_CHECK_LINE, 'if user_id is None or user_id == "":')]),
    ("the sub is trimmed", [("return user_id, None", "return user_id.strip(), None")]),
    ("the sub is changed to lower case", [("return user_id, None", "return user_id.lower(), None")]),
    ("true counts as a number", [(NUMBER_LINE, "if not isinstance(issued_at, int) or not isinstance(expires_at, int):")]),
    ("decimal numbers count as numbers", [(NUMBER_LINE, "if not isinstance(issued_at, (int, float)) or not isinstance(expires_at, (int, float)):")]),
    # Time
    ("iat in the future is not checked", [("if issued_at > now:", "if False:")]),
    ("iat equal to now is refused", [("if issued_at > now:", "if issued_at >= now:")]),
    ("a token is still valid at the moment exp is reached", [("if now >= expires_at:", "if now > expires_at:")]),
    ("a token expires one second early", [("if now >= expires_at:", "if now + 1 >= expires_at:")]),
    ("expiry is not checked", [("if now >= expires_at:", "if False:")]),
    ("a life of exactly 3600 seconds is refused", [(LIFE_LINE, "if expires_at - issued_at >= MAX_LIFETIME_SECONDS:")]),
    ("the life limit is not checked", [(LIFE_LINE, "if False:")]),
    ("the life is measured from now, not from iat", [(LIFE_LINE, "if expires_at - now > MAX_LIFETIME_SECONDS:")]),
    ("the real clock is not used", [("now = int(time.time())", "now = 0")]),
    # The key
    ("the key is not trimmed", [(r'key = raw.strip(b" \t\r\n")', "key = raw")]),
    ("the key length is counted before trimming", [("if len(key) < MIN_KEY_BYTES:", "if len(raw) < MIN_KEY_BYTES:")]),
    ("any key length is accepted", [("MIN_KEY_BYTES = 32", "MIN_KEY_BYTES = 0")]),
    ("a 16-byte key is accepted", [("MIN_KEY_BYTES = 32", "MIN_KEY_BYTES = 16")]),
    ("a 32-byte key is refused", [("MIN_KEY_BYTES = 32", "MIN_KEY_BYTES = 33")]),
    ("a missing key file crashes the checker", [(KEY_FILE_LINE, "except PermissionError:\n        return None")]),
    ("the checker creates a missing key", [(KEY_FILE_LINE, 'except OSError:\n        Path(key_path).parent.mkdir(parents=True, exist_ok=True)\n        Path(key_path).write_bytes(b"x" * 40)\n        return None')]),
    # Order of the checks
    ("an empty string does not count as 'no token'", [(" or token == \"\":", ":")]),
    ("a token of spaces counts as 'no token'", [(TOKEN_LINE, 'if token is None or token.strip() == "":')]),
    ("the key is judged before the token", [(
        '    if token is None or token == "":\n        return None, "no_token"\n\n    key = load_key(key_path)\n    if key is None:\n        return None, "no_key"\n',
        '    key = load_key(key_path)\n    if key is None:\n        return None, "no_key"\n\n    if token is None or token == "":\n        return None, "no_token"\n',
    )]),
]


def make_broken_copy(source, replacements, folder, number):
    # Returns the checker module with the replacements applied, loaded from a file in `folder`.
    for old_text, new_text in replacements:
        assert source.count(old_text) == 1, (
            "this text must occur exactly once in " + str(SOURCE_FILE) + ", but occurs "
            + str(source.count(old_text)) + " times:\n" + old_text
        )
        source = source.replace(old_text, new_text)
    path = folder / ("broken_copy_" + str(number) + ".py")
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("broken_copy_" + str(number), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    # Control first: the real file must pass, or the whole experiment means nothing.
    problems, _ = find_problems(authentication, with_single_changes=False)
    assert problems == [], "the real checker fails its own tests: " + str(problems[:3])

    source = SOURCE_FILE.read_text(encoding="utf-8")
    missed = []
    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        for number, (description, replacements) in enumerate(MISTAKES, start=1):
            module = make_broken_copy(source, replacements, folder, number)
            # The quick checks first. The slow one-character sweep only runs if they find nothing.
            problems, _ = find_problems(module, with_single_changes=False)
            if not problems:
                problems, _ = find_problems(module, with_single_changes=True)
            verdict = "caught" if problems else "MISSED"
            print(str(number).rjust(2), verdict, "-", description)
            if not problems:
                missed.append(description)

    print(len(MISTAKES) - len(missed), "of", len(MISTAKES), "planted mistakes caught.")
    assert missed == [], "the tests did not notice: " + "; ".join(missed)
    print("Break-the-checker checks passed.")


if __name__ == "__main__":
    main()
