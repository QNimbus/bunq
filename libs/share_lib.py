# share_lib.py

# Standard library imports
import os
from typing import Union

# Third-party imports
from bunq.sdk.exception.bunq_exception import BunqException
from bunq.sdk.model.generated.endpoint import UserPerson, UserCompany, UserLight, MonetaryAccountBank

# Local application/library imports
from libs.logger import setup_logger


logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


class ShareLib:
    """
    A class for sharing library functions.
    """

    _ERROR_COULD_NOT_FIND_IBAN_POINTER = "Could not determine IBAN for Monetary Account."

    _ECHO_USER = os.linesep + "   User"
    _ECHO_MONETARY_ACCOUNT = os.linesep + "   Monetary Accounts"

    _POINTER_TYPE_IBAN = "IBAN"

    @classmethod
    def get_first_pointer_iban(cls, monetary_account_bank: MonetaryAccountBank):
        """
        :rtype: object_.Pointer
        """

        for alias in monetary_account_bank.alias:
            if alias.type_ == cls._POINTER_TYPE_IBAN:
                return alias

        raise BunqException(cls._ERROR_COULD_NOT_FIND_IBAN_POINTER)

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

    @classmethod
    def print_all_monetary_account_bank(cls, all_monetary_account_bank: list[MonetaryAccountBank]):
        """
        :type all_monetary_account_bank: list[endpoint.MonetaryAccountBank]
        """

        print(cls._ECHO_MONETARY_ACCOUNT)

        for monetary_account_bank in all_monetary_account_bank:
            cls.print_monetary_account_bank(monetary_account_bank)

    @classmethod
    def print_monetary_account_bank(cls, monetary_account_bank: MonetaryAccountBank):
        """
        :param monetary_account_bank: MonetaryAccountBank
        """

        pointer_iban = cls.get_first_pointer_iban(monetary_account_bank)

        print(
            f"""
  ┌───────────────────┬────────────────────────────────────────────────────
  │ ID                │ {monetary_account_bank.id_}
  ├───────────────────┼────────────────────────────────────────────────────
  │ Description       │ {monetary_account_bank.description}
  ├───────────────────┼────────────────────────────────────────────────────
  │ IBAN              │ {pointer_iban.value}"""
        )

        if monetary_account_bank.balance is not None:
            print(
                f"""  ├───────────────────┼────────────────────────────────────────────────────
  │ Balance           │ {monetary_account_bank.balance.currency} {monetary_account_bank.balance.value}"""
            )

        print(f"  └───────────────────┴────────────────────────────────────────────────────")
