# user.py

# Standard library imports
from abc import ABC, abstractmethod
from typing import Optional

# Third-party imports
from flask_login import UserMixin

# Local application/library imports
# ...


# User model
class User(UserMixin):
    """
    Represents a user in the system.

    Attributes:
        id (str): The unique identifier of the user.
        username (str): The username of the user.
        active (bool): Indicates whether the user is active or not.
    """

    def __init__(self, id: str, username: str, active: bool = True):  # pylint: disable=redefined-builtin
        self.id = id
        self.username = username
        self._active = active

    @property
    def is_active(self) -> bool:
        """
        Checks if the user is active.

        Returns:
            bool: True if the user is active, False otherwise.
        """
        return self._active


class UserConnector(ABC):
    """
    Gets a user by ID.

    Args:
        user_id (str | int): The ID of the user.

    Returns:
        Optional[User]: The user object if found, None otherwise.
    """

    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticates a user.

        Args:
            username (str): The username of the user.
            password (str): The password of the user.

        Returns:
            Optional[User]: The user object if the credentials are correct, None otherwise.
        """
