# json_user.py

# Standard library imports
import os
import json
from pathlib import Path
from typing import Optional

# Third-party imports
# ...

# Local application/library imports
from .. import logger
from libs.crypto import verify_password
from libs.user import User, UserConnector


class JsonUserConnector(UserConnector):
    """A connector for managing user data stored in a JSON file."""

    def __init__(self, file_path: Path):
        """
        Initialize the JsonUserConnector.

        Args:
            file_path (Path): The path to the JSON file containing user data.
        """
        self.file_path = file_path
        self.users = self.load_users()

    def load_users(self) -> dict:
        """
        Load the user data from the JSON file.

        Returns:
            dict: A dictionary containing the user data.
        Raises:
            FileNotFoundError: If the file does not exist.
        """
        # Ensure self.file_path points to a file and exists
        if not self.file_path.is_file():
            raise FileNotFoundError(f"File {self.file_path} does not exist")

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            data = {}

        return data

    def get_user(self, user_id: str | int) -> Optional[User]:
        """
        Get a user by their ID.

        Args:
            user_id (str | int): The ID of the user.

        Returns:
            Optional[User]: The user object if found, None otherwise.
        """
        # If user_id is a string, convert it to an integer
        if isinstance(user_id, int):
            user_id = str(user_id)

        user_data = self.users.get(user_id)

        if user_data:
            return User(user_id, user_data["username"], user_data.get("active", True))

        return None

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user by their username and password.

        Args:
            username (str): The username of the user.
            password (str): The password of the user.

        Returns:
            Optional[User]: The user object if authenticated, None otherwise.
        """
        for user_id, user_data in self.users.items():
            if user_data["username"] == username:
                if verify_password(user_data["password"], password):
                    return User(str(user_id), username, user_data.get("active", True))
        return None
