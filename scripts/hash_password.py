#!/usr/bin/env -S python -W ignore

# hash_password.py

# Standard library imports
import argparse

# Third-party imports
# ...

# Local application/library imports
from libs.crypto import hash_password


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Hash a password")
    parser.add_argument("password", help="The password to hash")

    args = parser.parse_args()

    password = args.password
    print(hash_password(password))
