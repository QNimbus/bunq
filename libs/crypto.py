# crypto.py

# Standard library imports
# ..

# Third-party imports
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

# Local application/library imports
# ...

# Import logging
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


_password_hasher = PasswordHasher(type=Type.ID)


def hash_password(pwd: str) -> str:
    """
    Hashes the given password using a password hasher.

    Args:
        pwd (str): The password to be hashed.

    Returns:
        str: The hashed password.
    """
    return _password_hasher.hash(pwd)


def verify_password(stored_hash: str, provided_password: str) -> bool:
    """
    Verify if the provided password matches the stored hash.

    Args:
        stored_hash (str): The stored password hash.
        provided_password (str): The password to verify.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    try:
        _password_hasher.verify(stored_hash, provided_password)
        return True
    except VerifyMismatchError:
        return False
