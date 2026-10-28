import unittest

from src.passwords import hash_password, verify_password


class PasswordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "Example-only passphrase 123!"
        cls.record = hash_password(cls.password)

    def test_correct_password(self):
        self.assertTrue(verify_password(self.password, self.record))

    def test_password_is_matched_exactly(self):
        for password in (
            self.password.lower(),
            self.password + " ",
            " " + self.password,
            "Incorrect passphrase 123!",
        ):
            with self.subTest(password=password):
                self.assertFalse(verify_password(password, self.record))

    def test_random_salts(self):
        other = hash_password(self.password)
        self.assertNotEqual(other["salt"], self.record["salt"])
        self.assertNotEqual(other["hash"], self.record["hash"])
        self.assertTrue(verify_password(self.password, other))

    def test_length_boundaries_and_unicode(self):
        for password in ("a" * 15, "b" * 128, "\u0ba4" * 15):
            with self.subTest(length=len(password)):
                self.assertTrue(
                    verify_password(password, hash_password(password))
                )

    def test_invalid_passwords(self):
        for password in (None, 123, b"bytes", [], "", "a" * 14,
                         "a" * 129, "\ud800" * 15):
            with self.subTest(value=repr(password)):
                with self.assertRaises(ValueError):
                    hash_password(password)
                self.assertFalse(verify_password(password, self.record))

    def test_corrupted_records_fail_closed(self):
        records = [None, [], {}, {"hash": self.record["hash"]}]
        changes = [
            ("algorithm", "sha256"),
            ("iterations", True),
            ("iterations", 600000.0),
            ("iterations", 1),
            ("iterations", 10**12),
            ("salt", None),
            ("salt", "0" * 31),
            ("salt", "g" * 32),
            ("hash", "0" * 63),
            ("hash", "g" * 64),
        ]
        records.extend({**self.record, field: value}
                       for field, value in changes)
        records.append({**self.record, "unexpected": "field"})
        for record in records:
            with self.subTest(record=record):
                self.assertFalse(verify_password(self.password, record))

    def test_changed_hash_is_rejected(self):
        changed = dict(self.record)
        first = "0" if changed["hash"][0] != "0" else "1"
        changed["hash"] = first + changed["hash"][1:]
        self.assertFalse(verify_password(self.password, changed))

    def test_record_contains_no_plaintext_password(self):
        self.assertEqual(
            set(self.record), {"algorithm", "iterations", "salt", "hash"}
        )
        self.assertNotIn(self.password, str(self.record))


if __name__ == "__main__":
    unittest.main(verbosity=2)
