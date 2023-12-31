# argparser.py

# Standard library imports
import os
import argparse
import datetime

# Third-party imports
# ...

# Local application/library imports
from libs.app_actions import Action

# Import logging
from libs import logger  # pylint: disable=ungrouped-imports,unused-import

DEFAULT_BUNQ_CONFIGURATION_FILE_NAME = ".bunq.conf"


def parse_date(date_str):
    """
    Parses a date string in the format YYYY-MM-DD and returns a datetime object.

    Args:
        date_str (str): The date string to parse.

    Returns:
        datetime.datetime: The parsed datetime object.

    Raises:
        argparse.ArgumentTypeError: If the date string is not in the correct format.
    """
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")  # Adjust the date format as needed
        return date_obj
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD format.") from exc


class Range(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __eq__(self, other):
        return self.start <= other <= self.end

    def __contains__(self, item):
        return self.__eq__(item)

    def __iter__(self):
        yield self

    def __str__(self):
        return "[{0},{1}]".format(self.start, self.end)

    def __repr__(self) -> str:
        return self.__str__()


class CLIArgs:
    """
    This class represents the command-line arguments that can be passed to the application.
    """

    _PRODUCTION = "--production"
    _CONFIG_FILE_NAME = "--config-file"

    _ACTION_CREATE_CONFIG_API_KEY = "--api-key"
    _ACTION_CREATE_REQUEST_AMOUNT = "--amount"
    _ACTION_CREATE_PAYMENT_AMOUNT = "--amount"
    _ACTION_CREATE_PAYMENT_SOURCE = "--source-iban"
    _ACTION_CREATE_PAYMENT_DESTINATION_NAME = "--destination-name"
    _ACTION_CREATE_PAYMENT_DESTINATION_IBAN = "--destination-iban"
    _ACTION_CREATE_PAYMENT_DESCRIPTION = "--description"
    _ACTION_CREATE_PAYMENT_ALLOW_THIRD_PARTY = "--allow-third-party"
    _ACTION_SHOW_ACCOUNTS_INCLUDE_INACTIVE = "--include-inactive"
    _ACTION_EXPORT_PATH = "--path"
    _ACTION_EXPORT_STARTDATE = "--start-date"
    _ACTION_EXPORT_ENDDATE = "--end-date"

    def __init__(self, description: str = ""):
        self.parser = argparse.ArgumentParser(description=description)

        self.parser.add_argument(
            CLIArgs._PRODUCTION,
            action="store_true",
            default=os.environ.get("PRODUCTION", False),
        )

        self.parser.add_argument(
            CLIArgs._CONFIG_FILE_NAME,
            default=os.environ.get("BUNQ_CONF", None),
            help="Specify Bunq configuration file name.",
        )

        # Add subparsers for each action.
        self.subparsers = self.parser.add_subparsers(dest="action", required=True, help="Action to perform.")

        self.action_create_config_parser = self.subparsers.add_parser(Action.SHOW_USER.value, help="Show user information.")

        self.action_create_config_parser = self.subparsers.add_parser(Action.CREATE_CONFIG.value, help="Create configuration file.")

        self.action_export_parser = self.subparsers.add_parser(Action.EXPORT.value, help="Export data.")

        self.action_create_request_parser = self.subparsers.add_parser(Action.CREATE_REQUEST.value, help="Create request for payment.")

        self.action_create_payment_parser = self.subparsers.add_parser(Action.CREATE_PAYMENT.value, help="Create payment.")

        self.action_show_accounts_parser = self.subparsers.add_parser(Action.SHOW_ACCOUNTS.value, help="Show information abount all accounts.")

        self.action_remove_all_statements_parser = self.subparsers.add_parser(Action.REMOVE_ALL_STATEMENTS.value, help="Remove all existing statements.")

        self.action_create_config_parser.add_argument(
            CLIArgs._ACTION_CREATE_CONFIG_API_KEY,
            required=False,
            default=os.environ.get("API_KEY", None),
            help="Create a config using the provided api key.",
        )

        self.action_create_request_parser.add_argument(
            CLIArgs._ACTION_CREATE_REQUEST_AMOUNT,
            required=True,
            help="Amount to request.",
        )

        self.action_create_payment_parser.add_argument(
            CLIArgs._ACTION_CREATE_PAYMENT_AMOUNT,
            required=True,
            type=float,
            choices=[Range(0.01, 9999.99)],
            help="Amount to pay.",
        )

        self.action_create_payment_parser.add_argument(
            CLIArgs._ACTION_CREATE_PAYMENT_SOURCE,
            required=True,
            help="IBAN account to pay from.",
        )

        self.action_create_payment_parser.add_argument(
            CLIArgs._ACTION_CREATE_PAYMENT_DESTINATION_IBAN,
            required=True,
            help="IBAN account to pay to.",
        )

        self.action_create_payment_parser.add_argument(
            CLIArgs._ACTION_CREATE_PAYMENT_DESTINATION_NAME,
            required=True,
            help="Name  of account owner to pay to.",
        )

        self.action_create_payment_parser.add_argument(
            CLIArgs._ACTION_CREATE_PAYMENT_DESCRIPTION,
            required=True,
            help="Description to add to payment.",
        )

        self.action_create_payment_parser.add_argument(CLIArgs._ACTION_CREATE_PAYMENT_ALLOW_THIRD_PARTY, action="store_true", default=False, help="Allow payments to third party accounts.")

        self.action_show_accounts_parser.add_argument(
            CLIArgs._ACTION_SHOW_ACCOUNTS_INCLUDE_INACTIVE,
            action="store_true",
            required=False,
            help="Include inactive accounts.",
        )

        self.action_export_parser.add_argument(
            CLIArgs._ACTION_EXPORT_PATH,
            required=False,
            default=os.environ.get("EXPORT_PATH", "./data"),
            help="Exported statements path.",
        )

        self.action_export_parser.add_argument(
            CLIArgs._ACTION_EXPORT_STARTDATE,
            type=parse_date,
            required=True,
            help="Start date in YYYY-MM-DD format",
        )

        self.action_export_parser.add_argument(
            CLIArgs._ACTION_EXPORT_ENDDATE,
            type=parse_date,
            required=True,
            help="End date in YYYY-MM-DD format",
        )

        self.args = self.parser.parse_args()

    @property
    def is_production(self) -> bool:
        """
        Get the value of the 'production' option.

        Returns:
            A boolean indicating whether the 'production' option was specified.
        """
        return self.args.production

    # Setter methods for self.args.action
    @property
    def action(self) -> Action:
        """
        Get the value of the 'action' option.

        Returns:
            A string indicating the action to perform.
        """
        return Action(self.args.action)

    def get_amount(self) -> int:
        """
        Get the value of the 'amount' option.

        Returns:
            An integer indicating the amount.
        """
        return self.args.amount

    def get_api_key(self) -> str:
        """
        Get the value of the 'api-key' option.

        Returns:
            A string indicating the API key.
        """
        return self.args.api_key

    def get_config_file(self) -> str | None:
        """
        Get the value of the 'config-file' option.

        Returns:
            A string indicating the configuration file name.
        """
        return self.args.config_file

    def get_export_path(self) -> str:
        """
        Get the value of the 'path' option.

        Returns:
            A string indicating the export path.
        """
        return self.args.path

    def get_start_date(self) -> datetime.datetime:
        """
        Get the value of the 'start-date' option.

        Returns:
            A datetime object indicating the start date.
        """
        return self.args.start_date

    def get_end_date(self) -> datetime.datetime:
        """
        Get the value of the 'end-date' option.

        Returns:
            A datetime object indicating the end date.
        """
        return self.args.end_date
