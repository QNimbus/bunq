#!/usr/bin/env -S python -W ignore

# app.py

# Standard library imports
import os
import sys
import socket
from typing import Optional

# Third-party imports
from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.api_environment_type import ApiEnvironmentType

# Local application/library imports
from libs.date import cap_date
from libs.logger import setup_logger
from libs.argparser import Action, CLIArgs
from libs.utils import write_statement_to_file
from libs.exceptions import ConfigFileExistsError, PathNotWritableError
from libs.share_lib import ShareLib
from libs.bunq_lib import (
    BunqLib,
    Utilites,
    StatementFormat,
    RegionalFormat,
    RequestInquiryOptions,
    PaymentOptions,
    CounterParty,
)


class BunqApp:  # pylint: disable=too-few-public-methods
    """
    This class represents a command-line interface for the My App application.
    """

    def __init__(self, is_production: bool, action: Action):
        self.is_production = is_production
        self.action = action
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")

        # Set up the logger:
        self.logger = setup_logger(__name__, self.log_level)

    # Class factory method to create app runtime
    @classmethod
    def create(cls, is_production: bool, action: Action) -> "BunqApp":
        """
        Class factory method to create app runtime.

        Args:
            is_production (bool): Whether to run in production mode.
            action (Action): The action to perform.

        Returns:
            BunqApp: The BunqApp instance.
        """
        return cls(is_production, action)

    def run(self, **kwargs):
        """
        Run the command-line interface.
        """

        if self.is_production:
            self.logger.info("Running in production mode")
        else:
            self.logger.info("Running in sandbox mode")

        if self.action == Action.CREATE_CONFIG:
            if "api_key" not in kwargs or kwargs["api_key"] is None:
                raise KeyError("The '--api-key' argument is required but was not provided.")
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")

            api_key = kwargs["api_key"]
            config_file = kwargs["config_file"]

            self.create_config(config_file=config_file, api_key=api_key, overwrite=False)
            return

        if self.action == Action.SHOW_USER:
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")

            config_file = kwargs["config_file"]

            self.show_user(config_file=config_file)

            return

        if self.action == Action.SHOW_ACCOUNTS:
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")

            config_file = kwargs["config_file"]

            self.show_accounts(config_file=config_file, include_inactive=kwargs["include_inactive"])

            return

        if self.action == Action.EXPORT:
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")
            if "path" not in kwargs or kwargs["path"] is None:
                raise KeyError("The 'path' argument is required but was not provided.")
            if "start_date" not in kwargs or kwargs["start_date"] is None:
                raise KeyError("The 'start_date' argument is required but was not provided.")
            if "end_date" not in kwargs or kwargs["end_date"] is None:
                raise KeyError("The 'end_date' argument is required but was not provided.")

            config_file = kwargs["config_file"]
            path = kwargs["path"]
            date_start = cap_date(kwargs["start_date"]).strftime("%Y-%m-%d")
            date_end = cap_date(kwargs["end_date"]).strftime("%Y-%m-%d")

            self.export(
                config_file=config_file,
                date_start=date_start,
                date_end=date_end,
                path=path,
            )
            return

        if self.action == Action.REMOVE_ALL_STATEMENTS:
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")

            config_file = kwargs["config_file"]
            self.remove_all_statements(config_file=config_file)
            return

        if self.action == Action.CREATE_REQUEST:
            raise NotImplementedError(f"Action '{self.action}' not implemented")

        if self.action == Action.CREATE_PAYMENT:
            if "config_file" not in kwargs or kwargs["config_file"] is None:
                raise KeyError("The '--config-file' argument is required but was not provided.")
            if "amount" not in kwargs or kwargs["amount"] is None:
                raise KeyError("The 'amount' argument is required but was not provided.")
            if "description" not in kwargs or kwargs["description"] is None:
                raise KeyError("The 'description' argument is required but was not provided.")
            if "source_iban" not in kwargs or kwargs["source_iban"] is None:
                raise KeyError("The 'source_iban' argument is required but was not provided.")
            if "destination_name" not in kwargs or kwargs["destination_name"] is None:
                raise KeyError("The 'destination_name' argument is required but was not provided.")
            if "destination_iban" not in kwargs or kwargs["destination_iban"] is None:
                raise KeyError("The 'destination_iban' argument is required but was not provided.")

            config_file = kwargs["config_file"]
            amount = kwargs["amount"]
            description = kwargs["description"]
            source_iban = kwargs["source_iban"]
            destination_name = kwargs["destination_name"]
            destination_iban = kwargs["destination_iban"]
            allow_third_party = kwargs["allow_third_party"]

            self.create_payment(
                config_file=config_file,
                amount=amount,
                description=description,
                source_iban=source_iban,
                destination_name=destination_name,
                destination_iban=destination_iban,
                allow_third_party=allow_third_party,
            )
            return

        raise NotImplementedError(f"Action '{self.action}' not implemented")

    def create_request(
        self,
        config_file: str,
        amount: float,
        monetary_account_id: int,
        counterparty: CounterParty,
        options: RequestInquiryOptions,
    ):
        """
        Attempts to create a request for payment.
        """
        bunq = BunqLib(self.is_production, config_file)

        bunq.make_request(
            amount=amount,
            monetary_account_id=monetary_account_id,
            counterparty=counterparty,
            options=options,
        )

    def create_payment(
        self,
        *,
        config_file: str,
        amount: float,
        description: str,
        source_iban: Optional[str] = None,
        monetary_account_id: Optional[int] = None,
        destination_name: str,
        destination_iban: str,
        allow_third_party: bool = False,
    ):
        """
        Create a payment transaction.

        Args:
            config_file (str): The path to the configuration file.
            amount (float): The amount of the payment.
            description (str): The description of the payment.
            source_iban (str, optional): The IBAN of the source account. Either `source_iban` or `monetary_account_id` must be provided.
            monetary_account_id (int, optional): The monetary account ID of the source account. Either `source_iban` or `monetary_account_id` must be provided.
            destination_name (str): The name of the destination account.
            destination_iban (str): The IBAN of the destination account.
            allow_third_party (bool, optional): Flag indicating whether third-party payments are allowed. Defaults to False.

        Raises:
            ValueError: If the amount is not positive or if both or none of `source_iban` and `monetary_account_id` are provided.
            ValueError: If the source account with the provided IBAN or monetary account ID is not found.

        Returns:
            None
        """
        # Ensure amount is positive
        if amount <= 0:
            raise ValueError(f"Amount must be positive, got {amount}")

        if not (source_iban is None) != (monetary_account_id is None):
            raise ValueError("Exactly one of 'source_iban' or 'monetary_account_id' must be provided, not both or none.")

        bunq = BunqLib(self.is_production, config_file)
        accounts_by_id = Utilites.get_accounts_by_monetary_account_id(bunq)
        accounts_by_iban = Utilites.get_accounts_by_iban(bunq)

        if not allow_third_party and destination_iban not in accounts_by_iban.keys():
            raise ValueError(f"Destination account with IBAN '{destination_iban}' not found, if IBAN is correct, set '--allow-third-party' to allow third-party payments")

        if monetary_account_id is not None:
            if monetary_account_id not in accounts_by_id.keys():
                raise ValueError(f"Source account with monetary account id '{monetary_account_id}' not found")
        else:
            if source_iban not in accounts_by_iban.keys():
                raise ValueError(f"Source account with IBAN '{source_iban}' not found")
            monetary_account_id = accounts_by_iban[source_iban].id_

        payment_options: PaymentOptions = PaymentOptions(description=description, currency="EUR")
        counterparty: CounterParty = CounterParty(name=destination_name, iban=destination_iban)

        self.logger.info(
            f"Attempting to create payment of {amount} from {source_iban} ({accounts_by_id[monetary_account_id].description}) to {destination_iban} ({destination_name}) with description '{description}'"
        )

        # bunq.make_payment(amount=amount, options=payment_options, counterparty=counterparty, monetary_account_id=monetary_account_id)

    def export(
        self,
        config_file: str,
        date_start: str,
        date_end: str,
        path: str,
    ):
        """
        Attempts to export statements from the current user's Bunq account.

        Returns:
            None
        """
        bunq = BunqLib(self.is_production, config_file)
        user = bunq.user

        self.logger.info(f"Attempting to export all statements for user {user.display_name} ({user.id_})")

        accounts_active = bunq.get_all_accounts(only_active=True)

        self.logger.info(f"Found {len(accounts_active)} active accounts")

        # Loop over accounts 'accounts_active'
        for account in accounts_active:
            self.logger.info(f"Attempting to export statements for account '{account.description}' ({account.id_})")

            # Generate statement
            statement_id = bunq.create_statement(
                account.id_,
                date_start,
                date_end,
                StatementFormat.CSV,
                RegionalFormat.EUROPEAN,
            )

            # Export statement
            statement = bunq.get_statement(statement_id, account.id_)

            if statement is None:
                self.logger.warning(f"Statement for account '{account.description}' with statement id {statement_id} not found")
                continue

            statement_data = bunq.export_statement(statement.id_, account.id_)
            name = user.legal_name.split(" ")[0]
            filename = os.path.join(
                path,
                f"{name}.{account.description} - {statement.date_start} {statement.date_end} - export statement.{StatementFormat.CSV.value.lower()}",
            )

            write_statement_to_file(
                statement_data,
                filename,
                force=True,
            )

            bunq.delete_statement(statement.id_, account.id_)

            self.logger.info(f"Exported statement for account '{account.description}' to '{filename}'")

        bunq.update_context()

    def show_user(self, config_file: str):
        bunq = BunqLib(self.is_production, config_file)
        user = bunq.user

        ShareLib.print_user(user)

    def show_accounts(self, config_file: str, include_inactive: bool = False):
        bunq = BunqLib(self.is_production, config_file)
        user = bunq.user

        self.logger.info(f"Attempting to show all accounts for user {user.display_name} ({user.id_})")

        accounts = bunq.get_all_accounts(only_active=(not include_inactive))

        self.logger.info(f"Found {len(accounts)} accounts")

        ShareLib.print_all_monetary_account_bank(accounts)

    def create_config(self, config_file: str, api_key: str, overwrite: bool = False):
        """
        Create a configuration file.
        """

        self.logger.info("Attempting to creating configuration file")

        # Check if the config file already exists
        if not overwrite and os.path.exists(config_file):
            raise ConfigFileExistsError(f"Config file {config_file} already exists")

        # Check if the destination path is writeable
        if not os.access(os.path.dirname(os.path.abspath(config_file)), os.W_OK):
            raise PathNotWritableError(f"Destination path {os.path.dirname(config_file)} is not writeable")

        if self.is_production:
            api_context = ApiContext.create(
                ApiEnvironmentType(ApiEnvironmentType.PRODUCTION),
                api_key,
                socket.gethostname(),
            )
        else:
            api_context = ApiContext.create(
                ApiEnvironmentType(ApiEnvironmentType.SANDBOX),
                api_key,
                socket.gethostname(),
            )

        api_context.save(config_file)

        self.logger.info(f"Created configuration file {os.path.abspath(config_file)}")

    def remove_all_statements(self, config_file: str):
        """
        Removes all statements for all active accounts of the current user.
        """
        bunq = BunqLib(self.is_production, config_file)
        user = bunq.user

        self.logger.info(f"Attempting to remove all statements for user {user.display_name} ({user.id_})")

        accounts_active = bunq.get_all_accounts(only_active=True)

        self.logger.info(f"Found {len(accounts_active)} active accounts")

        # Loop over accounts 'accounts_active'
        for account in accounts_active:
            self.logger.info(f"Removing statements for account '{account.description}' ({account.id_})")

            bunq.delete_all_statements(account)

        bunq.update_context()


if __name__ == "__main__":
    cl = CLIArgs("Bunq CLI App")
    app = BunqApp(is_production=cl.is_production, action=cl.action)

    try:
        app.run(**cl.args.__dict__)
    except Exception as error:  # pylint: disable=broad-except
        app.logger.exception(error)
        sys.exit(1)
