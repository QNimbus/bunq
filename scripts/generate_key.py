#!/usr/bin/env -S python -W ignore

# generate_key.py

# Standard library imports
import os
import base64
import argparse

# Third-party imports
# ...

# Local application/library imports


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate a key")
    parser.add_argument("length", default=32, type=int, help="The requested key length (default 32)")

    args = parser.parse_args()

    length = args.length
    if length < 1:
        raise ValueError("The key length must be greater than zero")

    key = os.urandom(length)

    print(f"hex: {key.hex()}")
    print(f"bytes: {key}")
    print(f"base64: {base64.b64encode(key)}")
