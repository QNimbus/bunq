# bunq_lib.py

# Standard library imports
import os
from enum import Enum
from dataclasses import dataclass
from typing import Union, List, Dict

# Third-party imports
from bunq import ApiEnvironmentType, Pagination
from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.bunq_context import BunqContext
from bunq.sdk.exception.bunq_exception import BunqException
from bunq.sdk.model.generated.object_ import Amount, Pointer
from bunq.sdk.model.generated.endpoint import (
    User,
    UserPerson,
    UserCompany,
    UserLight,
    ExportStatement,
    ExportStatementContent,
    MonetaryAccountBank,
    MonetaryAccountJoint,
    MonetaryAccountSavings,
    RequestInquiry,
)

# Local application/library imports
from libs.log import setup_logger
from libs.exceptions import (
    StatementNotFoundError,
    ExportError,
    StatementDeletionError,
    StatementsRetrievalError,
)

logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


@dataclass
class CounterParty:
    """
    A class representing a counterparty in a transaction.

    Attributes:
    -----------
    name : str
        The name of the counterparty.
    iban : str
        The IBAN of the counterparty.
    """

    name: str
    iban: str


@dataclass
class RequestInquiryOptions:
    """
    A class representing options for creating a request inquiry.

    Attributes:
    -----------
    description : str
        The description of the request inquiry.
    currency : str, optional
        The currency of the request inquiry. Defaults to "EUR".
    """

    description: str
    currency: str = "EUR"


class StatementFormat(Enum):  # pylint: disable=too-few-public-methods
    """
    Enum to represent different formats of the statement.

    Attributes:
        CSV: A statement in CSV format.
        MT940: A statement in MT940 format.
        PDF: A statement in PDF format.
    """

    CSV = "CSV"
    MT940 = "MT940"
    PDF = "PDF"


class RegionalFormat(Enum):  # pylint: disable=too-few-public-methods
    """
    Enum to represent different regional formats of the statement.

    Attributes:
        EUROPEAN: A statement in European format.
        UK_US: A statement in UK/US format.
    """

    EUROPEAN = "EUROPEAN"
    UK_US = "UK_US"


class BunqLib:
    """
    A class that provides a wrapper around the bunq Python SDK, allowing for easier interaction with the bunq API.
    """

    _BUNQ_CONF_PRODUCTION = ".bunq.production.conf"
    _BUNQ_CONF_SANDBOX = ".bunq.sandbox.conf"

    _PAGINATION_DEFAULT_COUNT = 200

    _MONETARY_ACCOUNT_STATUS_ACTIVE = "ACTIVE"

    _ERROR_COULD_NOT_DETERMINE_CONF = "Could not determine bunq configuration file."

    def __init__(self, production_mode: bool = False, config_file: str = None):
        """
        Initializes a new instance of the BunqLib class.

        Args:
            production_mode (bool, optional): Whether to use the production environment or the sandbox environment. Defaults to False.
            config_file (str, optional): The path to the configuration file to use. Defaults to None.
        """
        self.user = None
        self.config_file = config_file if config_file else self.determine_bunq_conf_filename()
        self.env = ApiEnvironmentType.PRODUCTION if production_mode else ApiEnvironmentType.SANDBOX

        self.api_context = None
        self.setup_context()
        self.setup_current_user()

    def __eq__(self, other):
        if not isinstance(other, BunqLib):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self.config_file == other.config_file

    def __hash__(self):
        return hash(self.config_file)

    def setup_context(self) -> None:
        """
        Sets up the API context for the bunq SDK.

        :return: None
        """
        if self.api_context and self.api_context == BunqContext.api_context():
            return self.api_context

        if not os.path.isfile(self.config_file):
            raise BunqException(BunqLib._ERROR_COULD_NOT_DETERMINE_CONF)

        api_context = ApiContext.restore(self.config_file)
        api_context.ensure_session_active()
        api_context.save(self.config_file)
        BunqContext.load_api_context(api_context)

        self.api_context = BunqContext.api_context()

    def setup_current_user(self) -> None:
        """
        Retrieve and set the current user of the BunqLib instance.

        This method retrieves the current user of the BunqLib instance and sets it as the instance's user attribute.
        The user attribute can be of type UserPerson, UserCompany, or UserLight.

        :return: None
        """
        user = User.get().value.get_referenced_object()
        if isinstance(user, (UserPerson, UserCompany, UserLight)):
            self.user = user

    def update_context(self) -> None:
        """
        Update the Bunq API context after making changes and save the updated context to the config file.

        Returns:
            None
        """
        BunqContext.api_context().save(self.config_file)

    def determine_bunq_conf_filename(self) -> str:
        """
        Determine the filename for the bunq configuration based on the environment type.

        Returns:
            str: The filename for the bunq configuration.
        """
        if self.env == ApiEnvironmentType.PRODUCTION:
            return self._BUNQ_CONF_PRODUCTION

        return self._BUNQ_CONF_SANDBOX

    def get_current_user(self) -> Union[UserCompany, UserPerson]:
        """
        Returns the current user, which can be either a UserCompany or UserPerson object.
        """
        return self.user

    def get_all_accounts_bank(self, only_active: bool = False) -> List[MonetaryAccountBank]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts = MonetaryAccountBank.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: List[MonetaryAccountBank] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    def get_all_accounts_joint(self, only_active: bool = False) -> List[MonetaryAccountJoint]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts = MonetaryAccountJoint.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: List[MonetaryAccountJoint] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    def get_all_accounts_savings(self, only_active: bool = False) -> List[MonetaryAccountSavings]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts = MonetaryAccountSavings.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: List[MonetaryAccountSavings] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    def get_all_accounts(
        self, only_active: bool = False
    ) -> List[Union[MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings,]]:
        """
        Returns a list of all accounts for the current user.
        """
        accounts = []

        accounts.extend(self.get_all_accounts_bank(only_active))
        accounts.extend(self.get_all_accounts_joint(only_active))
        accounts.extend(self.get_all_accounts_savings(only_active))

        return accounts

    def create_statement(
        self,
        monetary_account_id: int,
        date_start: str,
        date_end: str,
        statement_format: StatementFormat = StatementFormat.CSV,
        regional_format: RegionalFormat = RegionalFormat.EUROPEAN,
    ) -> int:
        """
        Creates a statement based on the provided parameters.

        Parameters:
            monetary_account_id (int): The ID of the monetary account.
            date_start (str): The start date for the statement.
            date_end (str): The end date for the statement.
            statement_format (StatementFormat): The format of the statement. Defaults to CSV.
            regional_format (RegionalFormat): The regional format of the statement. Defaults to EUROPEAN.

        Returns:
            int: The value returned after creating the statement.
        """
        self.setup_context()

        # Create a statement
        return ExportStatement.create(
            monetary_account_id=monetary_account_id,
            date_start=date_start,
            date_end=date_end,
            statement_format=statement_format.value,
            regional_format=regional_format.value,
        ).value

    def create_request_inquiry(
        self,
        amount: float,
        monetary_account_id: int,
        counterparty: CounterParty,
        options: RequestInquiryOptions = None,
    ) -> int:
        """
        Creates a request inquiry based on the provided parameters.
        """
        self.setup_context()

        if options is None:
            options = RequestInquiryOptions(description="AUTO-GENERATED REQUEST")

        return RequestInquiry.create(
            amount_inquired=Amount(value=amount, currency=options.currency),
            counterparty_alias=Pointer(type_="IBAN", value=counterparty.iban, name=counterparty.name),
            monetary_account_id=monetary_account_id,
            description=options.description,
            allow_bunqme=False,
        ).value

    def get_statement(self, statement_id: int, monetary_account_id: int) -> ExportStatement:
        """
        Retrieve a statement from the Bunq API.

        Args:
            statement_id (int): The ID of the statement to retrieve.
            monetary_account_id (int): The ID of the monetary account associated with the statement.

        Returns:
            ExportStatement: The statement object retrieved from the Bunq API.
        """
        self.setup_context()

        # Get a statement
        try:
            return ExportStatement.get(statement_id, monetary_account_id).value
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(exc)
            return None

    def export_statement(self, statement_id: int, monetary_account_id: int) -> bytes:
        """
        Export the specified statement content as bytes.

        Parameters:
        - statement_id (int): The ID of the statement to be exported.
        - monetary_account_id (int): The ID of the associated monetary account.

        Returns:
        - bytes: The statement content in bytes.

        Raises:
        - StatementNotFoundError: If the statement is not found.
        - ExportError: If there is an error in exporting the statement content.

        Example:
        >>> statement = Statement()
        >>> content = statement.export_statement(1, 12345)
        """
        self.setup_context()

        try:
            statement = self.get_statement(statement_id, monetary_account_id)
            if statement is None:
                raise StatementNotFoundError(f"Statement with ID {statement_id} not found")

            content = ExportStatementContent.list(statement.id_, monetary_account_id).value
            return content

        except Exception as exc:
            raise ExportError(f"Error exporting statement: {exc}") from exc

    def delete_statement(self, statement_id: int, monetary_account_id: int) -> None:
        """
        Deletes a statement with the given statement_id and monetary_account_id.

        Args:
            statement_id (int): The ID of the statement to delete.
            monetary_account_id (int): The ID of the monetary account that the statement belongs to.

        Returns:
            None
        """
        self.setup_context()

        try:
            ExportStatement.delete(statement_id, monetary_account_id)
        except Exception as exc:
            raise StatementDeletionError(f"An error occurred while deleting statement {statement_id} for account id {monetary_account_id}: {exc}") from exc

    def get_all_statements(
        self,
        account: MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings,
    ) -> Dict[str, List[ExportStatement]]:
        """
        Retrieve all statements for a given account.

        Args:
            account (MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings): The account to retrieve statements for.

        Returns:
            Dict[str, List[ExportStatement]]: A dictionary containing the statements for the given account, with the account ID as the key.
        """
        self.setup_context()

        try:
            statements: List[ExportStatement] = list(ExportStatement.list(account.id_).value)
        except Exception as exc:
            raise StatementsRetrievalError(f"An error occurred while retrieving statements for account '{account.description}' ({account.id_}): {exc}") from exc

        return statements

    def delete_all_statements(
        self,
        account: MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings,
    ) -> None:
        """
        Deletes all statements for a given account.

        Args:
            account (MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings): The account to delete statements for.

        Returns:
            None

        Raises:
            StatementDeletionError: If there is an error in deleting the statements.
        """
        statements = self.get_all_statements(account)

        for statement in statements:
            self.delete_statement(statement.id_, account.id_)
