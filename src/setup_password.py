"""Trusted local administrator command for initial password setup."""

import getpass
import sys
import warnings

from src.authorization import load_users
from src.credentials import create_credentials, credential_path


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m src.setup_password <user_id>", file=sys.stderr)
        return 2

    user_id = sys.argv[1]
    try:
        users, rejected = load_users()
        if rejected:
            print("Setup stopped: fix invalid user records first.", file=sys.stderr)
            return 1
        if user_id not in users:
            print("Setup stopped: unknown user ID.", file=sys.stderr)
            return 1
        if credential_path(user_id).exists():
            print("Setup stopped: credentials already exist.", file=sys.stderr)
            return 1

        # Refuse to fall back to visibly echoed password input.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password (15-128 characters): ")
            confirmation = getpass.getpass("Confirm password: ")

        if password != confirmation:
            print("Passwords did not match; nothing saved.", file=sys.stderr)
            return 1

        create_credentials(user_id, password)
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("\nSetup cancelled or hidden input unavailable.", file=sys.stderr)
        return 1
    except FileExistsError:
        print("Setup stopped: credentials already exist.", file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError):
        print(
            "Setup failed. Use a valid password of 15-128 characters "
            "and check local credential storage.",
            file=sys.stderr,
        )
        return 1

    print("Password credentials created. No token was issued.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
