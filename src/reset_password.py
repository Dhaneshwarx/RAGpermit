"""Reset a user's password after hidden administrator authentication."""

import argparse
import getpass
import sqlite3
import sys
import warnings

from src.admin_access import is_admin
from src.audit import log_auth_failure
from src.authentication import AUTH_FAILED_MESSAGE
from src.credentials import check_credentials
from src.passwords import password_bytes
from src.user_admin import change


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("user_id", help="Account whose password will be reset")
    parser.add_argument("--admin", required=True, help="Administrator user ID")
    args = parser.parse_args(argv)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            current = getpass.getpass("Current administrator password: ")
            authenticated = check_credentials(args.admin, current)
            del current
            if not authenticated or not is_admin(args.admin):
                try:
                    log_auth_failure("password_reset_auth_failed")
                except Exception:
                    pass
                print(AUTH_FAILED_MESSAGE, file=sys.stderr)
                return 1

            password = getpass.getpass("New password (3-20 characters): ")
            confirmation = getpass.getpass("Confirm new password: ")

        if password != confirmation:
            print("Passwords did not match; nothing changed.", file=sys.stderr)
            return 1
        password_bytes(password)
        change(args.admin, {
            "action": "reset", "user_id": args.user_id, "password": password,
        })
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("\nReset cancelled or hidden input unavailable.", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, RecursionError, sqlite3.Error):
        print(
            "Reset could not be completed. Check the account, administrator access, "
            "password length (3-20 characters), and local storage.",
            file=sys.stderr,
        )
        return 1

    print("Password reset. Previous sessions for this account were revoked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
