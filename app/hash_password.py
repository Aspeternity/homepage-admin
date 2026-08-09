from __future__ import annotations

import getpass
import sys

import bcrypt


def main() -> None:
    password = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must contain at least 8 characters.")
    print(bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8"))


if __name__ == "__main__":
    main()
