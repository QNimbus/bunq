# bunq_lib.py

# Standard library imports
import os
import json
from enum import Enum
from typing import Union
from dataclasses import dataclass

# Third-party imports
from bunq import ApiEnvironmentType, Pagination
from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.bunq_context import BunqContext
from bunq.sdk.model.generated.object_ import Amount, Pointer
from bunq.sdk.model.generated.endpoint import (
    User,
    UserPerson,
    UserCompany,
    UserLight,
    Payment,
    ExportStatement,
    ExportStatementContent,
    MonetaryAccountBank,
    MonetaryAccountJoint,
    MonetaryAccountSavings,
    RequestInquiry,
)

# Local application/library imports
from libs.logger import setup_logger
from libs.redis_wrapper import redis_memoize, JsonSerializer
from libs.exceptions import (
    BunqLibError,
    ExportError,
    StatementNotFoundError,
    StatementDeletionError,
    StatementsRetrievalError,
)

# Constants
REDIS_MEMOIZE_EXPIRATION_TIME = 60 * 60 * 24  # 24 hours

logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


class MonetaryAccountSerializer(JsonSerializer):
    """
    A class that implements the JsonSerializer interface for the MonetaryAccountBank class.
    """

    @classmethod
    def serialize(cls, obj: list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]) -> str:
        """
        Serialize an array of MonetaryAccountBank, MonetaryAccountJoint or MonetaryAccountSavings objects to a JSON string.

        Args:
            obj (list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]): The array of objects to serialize.

        Returns:
            str: The JSON string representation of the serialized array.
        """

        def custom_serializer(obj):
            """
            Custom serializer function for JSON serialization.

            Args:
                obj: The object to be serialized.

            Returns:
                The serialized JSON representation of the object.

            Raises:
                TypeError: If the object is not of type MonetaryAccountBank, MonetaryAccountJoint or MonetaryAccountSavings.
            """
            if isinstance(obj, (MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings)):
                obj_json = []

                # Get the class name of the object
                obj_json.append(obj.__class__.__name__)

                # Get the JSON representation of the object
                obj_json.append(obj.to_json())

                return obj_json

            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

        return json.dumps(obj, default=custom_serializer)

    @classmethod
    def deserialize(cls, json_string: str) -> list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]:
        """
        Deserialize a JSON string to an array of MonetaryAccountBank, MonetaryAccountJoint or MonetaryAccountSavings objects.

        Args:
            json_string (str): The JSON string to deserialize.

        Returns:
            list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]: The deserialized array of objects.
        """
        parsed_data = json.loads(json_string)
        deserialized_objects = []

        for item in parsed_data:
            object_class = item[0]
            object_data = item[1]

            if object_class == "MonetaryAccountBank":
                deserialized_objects.append(MonetaryAccountBank.from_json(object_data))
            elif object_class == "MonetaryAccountJoint":
                deserialized_objects.append(MonetaryAccountJoint.from_json(object_data))
            elif object_class == "MonetaryAccountSavings":
                deserialized_objects.append(MonetaryAccountSavings.from_json(object_data))

        return deserialized_objects


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


@dataclass
class PaymentOptions:
    """
    A class representing options for creating a payment.

    Attributes:
    -----------
    description : str
        The description of the payment.
    currency : str, optional
        The currency of the payment. Defaults to "EUR".
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
        self._max_payment_amount = float(os.environ.get("MAX_PAYMENT_AMOUNT", 1.00))

        self._user = None
        self.config_file = config_file if config_file else self.determine_bunq_conf_filename()
        self.env = ApiEnvironmentType.PRODUCTION if production_mode else ApiEnvironmentType.SANDBOX

        self.api_context = None
        self.setup_context()
        self.setup_current_user()

    def __eq__(self, other):
        if not isinstance(other, BunqLib):
            # don't attempt to compare against unrelated types
            return NotImplemented

        return self._user._id == self._user._id

    def __repr__(self):
        return f"BunqLib(user_id={self._user.id_})"

    @property
    def max_payment_amount(self) -> float:
        """
        Returns the maximum payment amount.
        """
        return self._max_payment_amount

    def setup_context(self) -> None:
        """
        Sets up the API context for the bunq SDK.

        :return: None
        """
        if self.api_context and self.api_context == BunqContext.api_context():
            return self.api_context

        if not os.path.isfile(self.config_file):
            raise BunqLibError(self._ERROR_COULD_NOT_DETERMINE_CONF)

        # If file is not readable or writable, bunq will throw an exception
        if not os.access(self.config_file, os.R_OK | os.W_OK):
            raise BunqLibError(f"Configuration file {self.config_file} is not readable or writable.")

        api_context = ApiContext.restore(self.config_file)
        api_context.ensure_session_active()
        api_context.save(self.config_file)
        BunqContext.load_api_context(api_context)

        self.api_context = BunqContext.api_context()
        return self.api_context

    def setup_current_user(self) -> None:
        """
        Retrieve and set the current user of the BunqLib instance.

        This method retrieves the current user of the BunqLib instance and sets it as the instance's user attribute.
        The user attribute can be of type UserPerson, UserCompany, or UserLight.

        :return: None
        """
        user = User.get().value.get_referenced_object()
        if isinstance(user, (UserPerson, UserCompany, UserLight)):
            self._user = user

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

    @redis_memoize(expiration_time=REDIS_MEMOIZE_EXPIRATION_TIME, instance_identifier="user_id", serializer=MonetaryAccountSerializer)
    def get_all_accounts_bank(self, only_active: bool = False) -> list[MonetaryAccountBank]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts: list[MonetaryAccountBank] = MonetaryAccountBank.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: list[MonetaryAccountBank] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    @redis_memoize(expiration_time=REDIS_MEMOIZE_EXPIRATION_TIME, instance_identifier="user_id", serializer=MonetaryAccountSerializer)
    def get_all_accounts_joint(self, only_active: bool = False) -> list[MonetaryAccountJoint]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts: list[MonetaryAccountJoint] = MonetaryAccountJoint.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: list[MonetaryAccountJoint] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    @redis_memoize(expiration_time=REDIS_MEMOIZE_EXPIRATION_TIME, instance_identifier="user_id", serializer=MonetaryAccountSerializer)
    def get_all_accounts_savings(self, only_active: bool = False) -> list[MonetaryAccountSavings]:
        """
        Returns a list of all accounts for the current user.
        """
        self.setup_context()

        pagination = Pagination()
        pagination.count = self._PAGINATION_DEFAULT_COUNT

        accounts: list[MonetaryAccountSavings] = MonetaryAccountSavings.list(pagination.url_params_count_only).value

        if only_active:
            accounts_active: list[MonetaryAccountSavings] = []

            for account in accounts:
                if account.status == self._MONETARY_ACCOUNT_STATUS_ACTIVE:
                    accounts_active.append(account)

            return accounts_active

        return accounts

    def get_all_accounts(self, only_active: bool = False) -> list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]:
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

    def make_payment(
        self,
        amount: float,
        monetary_account_id: int,
        counterparty: CounterParty,
        options: PaymentOptions = None,
    ) -> int:
        # Check if amount is positive and less than the maximum payment amount
        if amount <= 0 or amount > self.max_payment_amount:
            raise ValueError(f"Amount must be positive and less than {self.max_payment_amount}")

        self.setup_context()

        if options is None:
            options = PaymentOptions(description="AUTO-GENERATED PAYMENT")

        return Payment.create(
            amount=Amount(value=amount, currency=options.currency),
            counterparty_alias=Pointer(type_="IBAN", value=counterparty.iban, name=counterparty.name),
            description=options.description,
            monetary_account_id=monetary_account_id,
        ).value

    def make_request(
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
    ) -> dict[str, list[ExportStatement]]:
        """
        Retrieve all statements for a given account.

        Args:
            account (MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings): The account to retrieve statements for.

        Returns:
            dict[str, list[ExportStatement]]: A dictionary containing the statements for the given account, with the account ID as the key.
        """
        self.setup_context()

        try:
            statements: list[ExportStatement] = list(ExportStatement.list(account.id_).value)
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

    @property
    def user(self) -> Union[UserCompany, UserPerson]:
        """
        Returns the current user, which can be either a UserCompany or UserPerson object.
        """
        return self._user

    @property
    def user_id(self) -> int:
        """
        Returns the ID of the current user.
        """
        return self._user.id_


class Utilites:
    """
    Utility class for payment processing operations.
    """

    @staticmethod
    def get_accounts_by_monetary_account_id(bunq_lib: BunqLib) -> dict[int, list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]]:
        """
        Get the accounts associated with the user from the Bunq library.

        Args:
            bunq_lib (BunqLib): The Bunq library instance.

        Returns:
            dict: A dictionary containing the monetary account IDs as keys and the corresponding accounts as values.
        """
        accounts: dict[str, list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]]
        accounts = {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}

        return accounts

    @staticmethod
    def get_accounts_by_iban(bunq_lib: BunqLib) -> dict[str, list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]]:
        """
        Get the accounts associated with the user from the Bunq library.

        Args:
            bunq_lib (BunqLib): The Bunq library instance.

        Returns:
            dict: A dictionary containing the IBANs as keys and the corresponding accounts as values.
        """
        accounts: dict[str, list[MonetaryAccountBank | MonetaryAccountJoint | MonetaryAccountSavings]]
        accounts = {alias.value: account for account in bunq_lib.get_all_accounts(only_active=True) for alias in account.alias if alias.type_ == "IBAN"}

        return accounts
