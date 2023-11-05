# share_lib.py

# Standard library imports
import os
from typing import Union

# Third-party imports
from bunq.sdk.model.generated.endpoint import UserPerson, UserCompany, UserLight

# Local application/library imports
from libs.log import setup_logger


logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


class ShareLib:
    """
    A class for sharing library functions.
    """

    _ECHO_USER = os.linesep + "   User"

    @classmethod
    def print_user(cls, user: Union[UserPerson, UserCompany, UserLight]):
        """
        Prints user information.

        Args:
            user (Union[UserPerson, UserCompany, UserLight]): The user to print information for.
        """
        print(cls._ECHO_USER)
        print(
            f"""
  ┌───────────────────┬────────────────────────────────────────────────────
  │ ID                │ {user.id_}
  ├───────────────────┼────────────────────────────────────────────────────
  │ Username          │ {user.display_name}
  └───────────────────┴────────────────────────────────────────────────────"""
        )
