# action.py

# Standard library imports
from enum import Enum

# Third-party imports
# ...

# Local application/library imports
# ...


class Action(Enum):
    """
    An enumeration of the available actions that can be performed by the application.
    """

    EXPORT = "export"
    SHOW_USER = "show-user"
    SHOW_ACCOUNTS = "show-accounts"
    CREATE_CONFIG = "create-config"
    CREATE_REQUEST = "create-request"
    REMOVE_ALL_STATEMENTS = "remove-all-statements"
