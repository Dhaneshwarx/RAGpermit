# Tests for src/authentication.py   (policy: data/POLICY.md, section 6)
#
# The answer key is tests/token_cases.csv. It was written by hand from the policy BEFORE the
# checker existed, so the checker is judged by the policy and not by itself.
# Tokens come from tests/token_builders.py. The clock is frozen, so no test depends on today's date.
#
# Run:  python -m tests.test_auth

import csv
import tempfile
import time
from pathlib import Path

import src.authentication as authentication
from tests.token_builders import ALPHABET, GOOD_KEY, NOW, build_cases, make_token, payload_dict

CASES_FILE = Path("tests/token_cases.csv")
USER_NAMES = ["Premkumar", "Deepak", "Srikanth", "Yash", "Mahasri", "Dhanesh"]
FAILURE_REASONS = {
    "no_token", "no_key", "malformed", "bad_alg", "bad_signature",
    "bad_claims", "not_yet_valid", "expired", "lifetime_too_long",
}

# Characters tried in place of, or inserted into, a valid token: every legal character plus
# the dangerous ones (dot, padding, the standard-base64 symbols, stray characters, a non-ASCII letter).
TRY_CHARACTERS = ALPHABET + ".=+/* \t\n" + chr(233)   # chr(233) is the letter e with an accent
INSERT_CHARACTERS = "A-*= "


def read_rows(path):
    with open(path, encoding="ascii", newline="") as file:
        return list(csv.DictReader(file))


def write_key(folder, name, key_bytes):
    key_path = folder / name / "keys" / "token_key.txt"
    key_path.parent.mkdir(parents=True)
    key_path.write_bytes(key_bytes)
    return key_path


def check_answer_key(module, folder):
    # Every row of the answer key: build the token, run the checker, compare with the key.
    problems = []
    rows = read_rows(CASES_FILE)
    cases = build_cases()
    if sorted(row["case_id"] for row in rows) != sorted(cases):
        problems.append("the CSV and the token builders list different cases")
        return problems, len(rows)

    for row in rows:
        case_id = row["case_id"]
        token, key_file = cases[case_id]
        # The keys folder is NOT created for a row without a key file. That lets us see
        # whether the checker wrongly creates one.
        key_path = folder / case_id / "keys" / "token_key.txt"
        if key_file is not None:
            write_key(folder, case_id, key_file)

        if row["expected"] == "valid":
            wanted = (row["expected_sub"], None)
        else:
            wanted = (None, row["expected"])
        try:
            got = module.authenticate(token, now=NOW, key_path=key_path)
        except Exception as error:
            got = "crash: " + type(error).__name__
        if got != wanted:
            problems.append(case_id + ": wanted " + str(wanted) + ", got " + str(got))

        if key_file is None and (key_path.exists() or key_path.parent.exists()):
            problems.append(case_id + ": the checker created a key or a keys folder")
    return problems, len(rows)


def check_sub_as_written(module, folder):
    # Policy: "The sub value is used exactly as written." Not trimmed, not changed to another case.
    problems = []
    key_path = write_key(folder, "sub", GOOD_KEY)
    for sub in [" Srikanth ", "SRIKANTH", "srikanth\n", "Zo" + chr(235)]:
        token = make_token(payload=payload_dict(sub))
        got = module.authenticate(token, now=NOW, key_path=key_path)
        if got != (sub, None):
            problems.append("sub " + repr(sub) + " came back as " + str(got))
    return problems


def check_not_text(module, folder):
    # Not a policy case: a program (not a person) might pass something that is not text at all.
    # It must fail closed.
    problems = []
    key_path = write_key(folder, "not-text", GOOD_KEY)
    for value in [123, b"abc.def.ghi", ["a", "b", "c"], {}]:
        try:
            got = module.authenticate(value, now=NOW, key_path=key_path)
        except Exception as error:
            got = "crash: " + type(error).__name__
        if got != (None, "malformed"):
            problems.append(repr(value) + " was not refused as malformed: " + str(got))
    return problems


def check_real_clock(module, folder):
    # When no `now` is given, the checker must use the real clock.
    problems = []
    key_path = write_key(folder, "clock", GOOD_KEY)
    seconds = int(time.time())
    fresh = make_token(payload=payload_dict("Deepak", iat=seconds - 5, exp=seconds + 600))
    stale = make_token(payload=payload_dict("Deepak", iat=seconds - 2000, exp=seconds - 1000))
    if module.authenticate(fresh, key_path=key_path) != ("Deepak", None):
        problems.append("a token that is valid right now was refused")
    if module.authenticate(stale, key_path=key_path) != (None, "expired"):
        problems.append("a token that expired long ago was not refused as expired")
    return problems


def check_deep_nesting(module, folder):
    # JSON nested 200,000 levels deep makes Python raise RecursionError, which is NOT a ValueError.
    # The 2048-character limit normally stops such a token first, so this check lifts the limit
    # for a moment to prove that the line which catches RecursionError really works.
    problems = []
    key_path = write_key(folder, "deep", GOOD_KEY)
    token = make_token(payload_bytes=b"[" * 200_000 + b"]" * 200_000)
    original_limit = module.MAX_TOKEN_LENGTH
    module.MAX_TOKEN_LENGTH = 10_000_000
    try:
        got = module.authenticate(token, now=NOW, key_path=key_path)
    except Exception as error:
        got = "crash: " + type(error).__name__
    finally:
        module.MAX_TOKEN_LENGTH = original_limit
    if got != (None, "malformed"):
        problems.append("a token with absurdly deep JSON was not refused as malformed: " + str(got))
    return problems


def check_constant_time_source(module):
    # Timing cannot be seen from outside, so this one check reads the source:
    # the signature must be compared with hmac.compare_digest, not with ==.
    source = Path(module.__file__).read_text(encoding="utf-8")
    if "hmac.compare_digest(parts[2], expected)" not in source:
        return ["the signature is not compared with hmac.compare_digest"]
    return []


def check_single_changes(module, folder):
    # Policy: "changing any single character of a token makes it invalid, even a character that
    # would decode to the same bytes." We take a valid token for each user and try every
    # one-character replacement, every one-character deletion and a few one-character insertions.
    problems = []
    key_path = write_key(folder, "single", GOOD_KEY)
    tried = 0
    for name in USER_NAMES:
        token = make_token(payload=payload_dict(name))
        if module.authenticate(token, now=NOW, key_path=key_path) != (name, None):
            problems.append("control failed: the unchanged token for " + name + " was refused")
            continue

        variants = []
        for position in range(len(token)):
            for character in TRY_CHARACTERS:
                if character != token[position]:
                    variants.append(token[:position] + character + token[position + 1:])
            variants.append(token[:position] + token[position + 1:])
            for character in INSERT_CHARACTERS:
                variants.append(token[:position] + character + token[position:])

        for variant in variants:
            tried += 1
            try:
                got = module.authenticate(variant, now=NOW, key_path=key_path)
            except Exception as error:
                got = "crash: " + type(error).__name__
            if not (isinstance(got, tuple) and got[0] is None and got[1] in FAILURE_REASONS):
                problems.append("a one-character change was accepted or crashed: " + repr(variant) + " -> " + str(got))
                if len(problems) > 10:
                    return problems, tried
    return problems, tried


def find_problems(module, with_single_changes=True):
    # Runs every check against `module` (the real checker, or a copy with a planted mistake).
    # Returns (list of problems, dict of counts). An empty list means the module passed everything.
    problems = []
    counts = {}
    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        found, counts["rows"] = check_answer_key(module, folder)
        problems += found
        problems += check_sub_as_written(module, folder)
        problems += check_not_text(module, folder)
        problems += check_real_clock(module, folder)
        problems += check_deep_nesting(module, folder)
        problems += check_constant_time_source(module)
        if with_single_changes:
            found, counts["single changes"] = check_single_changes(module, folder)
            problems += found
    return problems, counts


def main():
    problems, counts = find_problems(authentication)
    for problem in problems[:20]:
        print("PROBLEM:", problem)
    assert problems == [], str(len(problems)) + " problem(s): see above"
    print(counts["rows"], "answer-key rows agree with the checker.")
    print(counts["single changes"], "one-character changes tried: none was accepted.")
    print("Authentication checks passed.")


if __name__ == "__main__":
    main()
