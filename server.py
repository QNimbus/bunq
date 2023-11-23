# server.py

# Standard library imports
import os
import json
from typing import Union
from functools import cache

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, jsonify, request, current_app

# Local application/library imports
from libs.bunq_lib import (
    BunqLib,
    CounterParty,
    RequestInquiryOptions,
    MonetaryAccountBank,
    MonetaryAccountJoint,
    MonetaryAccountSavings,
)
from libs.log import setup_logger, setup_logger_with_rotating_file_handler
from libs.decorator import route, routes
from libs.rules import process_rules, load_rules, get_nested_property
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware
from schema.rules_model import Rules, Action
from schema.callback_model import (
    CallbackModel,
    EventType,
    PaymentType,
    RequestInquiryType,
    RequestResponseType,
    MasterCardActionType,
)


# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))
callback_logger = setup_logger_with_rotating_file_handler(
    "callback",
    log_level="INFO",
    filename="data/callback.log",
    max_bytes=100 * 1024 * 1024,
    backup_count=5,
)


# @cache
def get_all_accounts(
    bunq_lib: BunqLib,
) -> dict[str, Union[MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings]]:
    # Create a dictionary of accounts with the account id as key
    return {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}


def process_payment(
    app: Flask,
    event_type: EventType,
    data: PaymentType | RequestInquiryType | RequestResponseType | MasterCardActionType | None,
) -> None:
    """
    Process a payment created notification and create a request in Bunq if the payment matches the rules.

    Args:
        app (Flask): The Flask app instance.
        data (CallbackModel): The notification data.

    Returns:
        None
    """
    # Return early if data is None
    if data is None:
        return

    logger.debug(f"{event_type.value}: {data}")

    bunq_accounts: list[BunqLib] = current_app.config["BUNQ_ACCOUNTS"]
    rule_collections: dict[str, Rules] = app.config["RULES"]

    for rules_file, rules in rule_collections.items():
        logger.debug(f"Processing rule: {rules_file}")

        action: Action
        success, action, rule_name, rule_description = process_rules(event_type=event_type, data=data, rules=rules)

        # If the rule is not successful or no action is found, continue to the next rule
        if not success or action is None:
            continue

        # If data is type of PaymentType:
        if isinstance(data, PaymentType):
            if action.type.value == "CREATE_REQUEST_FROM_PAYMENT":
                monetary_account_id = data.monetary_account_id
                # Loop over BunqLib instances
                for bunq_lib in bunq_accounts:
                    # Create array of monetary account ids from accounts list
                    accounts = get_all_accounts(bunq_lib)

                    # If the monetary account id is found in the accounts list, create a request
                    if monetary_account_id in accounts.keys():
                        account = accounts[monetary_account_id]
                        logger.info(
                            f"{event_type.value}: {account.display_name} - '{data.description}' matches '{rule_name}::{rule_description}' rules in {rules_file}"
                        )

                        action_create_request_from_payment(bunq=bunq_lib, action=action, payment=data)
                        break


def process_unregistered_event(app: Flask, event_type: EventType, data: any) -> None:  # pylint: disable=unused-argument
    """
    Process an unregistered event type.

    Args:
        app (Flask): The Flask application instance.
        data (any): The data associated with the unregistered event.

    Returns:
        None
    """
    logger.debug(f"Unregistered event type: {event_type}")


def action_create_request_from_payment(bunq: BunqLib, action: Action, payment: PaymentType) -> None:
    description = action.data.description
    counterparty = CounterParty(
        name=action.data.request_from.name,
        iban=action.data.request_from.iban,
    )
    make_abs = action.data.amount_value_absolute
    amount = float(get_nested_property(payment.model_dump(), action.data.amount_value_property))

    if (make_abs is not None) and make_abs:
        amount = abs(amount)

    if action.data.append_original_description:
        description = f"{description} - {payment.description}"

    bunq.create_request_inquiry(
        amount=amount,
        counterparty=counterparty,
        monetary_account_id=payment.monetary_account_id,
        options=RequestInquiryOptions(description=description),
    )


@route("/health", methods=["GET"])
def health():
    """
    Handles health check requests via HTTP GET.

    Parameters:
    - None

    Returns:
    - JSON response with a success message.
    """
    return jsonify({"message": "Success"}, 200)


@route("/callback", methods=["POST"])
def callback():
    """
    Handles callbacks from another application via HTTP POST.

    Parameters:
    - None

    Returns:
    - JSON response with a success message if the request is valid and from an allowed IP.
    """
    # Return 400 if the request is not JSON
    if not request.is_json:
        return jsonify({"message": "Invalid request"}), 400

    try:
        request_data = request.get_json()
        request_schema = current_app.config["CALLBACK_SCHEMA"]

        # Log the json data
        callback_logger.info(json.dumps(request_data))

        # Validate the request data against the schema
        validate(instance=request_data, schema=request_schema)

        # Log callback data
        logger.debug(f"Callback data: {json.dumps(request_data)}")

        callback_data = TypeAdapter(CallbackModel).validate_python(request_data)
        event_type = callback_data.NotificationUrl.event_type

        # Dictionary to simulate a switch/case structure
        switcher = {
            "PAYMENT_CREATED": (process_payment, "Payment"),
            "PAYMENT_RECEIVED": (process_payment, "Payment"),
            "MUTATION_CREATED": (process_payment, "Payment"),
            "MUTATION_RECEIVED": (process_payment, "Payment"),
            "CARD_PAYMENT_ALLOWED": (None, None),
            "CARD_TRANSACTION_NOT_ALLOWED": (None, None),
            "REQUEST_INQUIRY_CREATED": (None, None),
            "REQUEST_INQUIRY_ACCEPTED": (None, None),
            "REQUEST_INQUIRY_REJECTED": (None, None),
            "REQUEST_RESPONSE_CREATED": (None, None),
            "REQUEST_RESPONSE_ACCEPTED": (None, None),
            "REQUEST_RESPONSE_REJECTED": (None, None),
        }

        # Get the function from switcher dictionary
        handler, data_object = switcher.get(event_type.value, process_unregistered_event)

        # Execute the function if handler is not None:
        if handler is not None:
            handler(
                app=current_app,
                event_type=event_type,
                data=callback_data.NotificationUrl.object.root.Payment,
            )

        return jsonify({"message": "Success"})
    except ValidationError:
        # Log failed schema validation
        logger.debug(f"Callback data failed validation: {json.dumps(request_data)}")

        return jsonify({"message": "Invalid request"}), 400


def create_server(allowed_ips: list[str] = None) -> Flask:
    """
    Starts the Flask server.

    Returns:
        None
    """
    logger.info("Starting server")

    if allowed_ips is None:
        if os.environ.get("ALLOWED_IPS", None) is None:
            allowed_ips = []
        else:
            allowed_ips = os.environ.get("ALLOWED_IPS").split(",")

    logger.info(f"Allowed IPs: {allowed_ips}")

    # Load the rules schema from an external file
    rules_schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema/rules.schema.json")
    with open(rules_schema_file, "r", encoding="utf-8") as file:
        rules_schema = json.load(file)

    # Load the rules from external files
    rules: Rules = {}
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules/")
    for file in os.listdir(rules_dir):
        if file.endswith("rules.json"):
            rules_file = os.path.join(rules_dir, file)
            rules[file] = load_rules(schema=rules_schema, rules_path=rules_file)
            logger.info(f"Loaded rules from {rules_file}")

    # Load the callback schema from an external file
    callback_schema_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema/callback.schema.json")
    with open(callback_schema_file, "r", encoding="utf-8") as file:
        callback_schema: CallbackModel = json.load(file)

    # Initialize BunqApp instances
    bunq_accounts: list[BunqLib] = []
    conf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf/")
    for file in os.listdir(conf_dir):
        if file.endswith(".conf"):
            conf_file = os.path.join(conf_dir, file)
            bunq_accounts.append(BunqLib(production_mode=True, config_file=conf_file))
            logger.info(f"Initialized BunqLib with config file: {conf_file}")

    # Create the Flask application
    app = Flask(__name__)

    # Store schema in app session
    app.config["RULES"] = rules
    app.config["BUNQ_ACCOUNTS"] = bunq_accounts
    app.config["CALLBACK_SCHEMA"] = callback_schema

    # Register stored routes
    for rule, f, options in routes:
        app.route(rule, **options)(f)

    # Register middlewares
    app.wsgi_app = AllowedIPsMiddleware(
        app=app.wsgi_app,
        allowed_ips=allowed_ips,
        trust_proxy=True,
        public_routes=["/health"],
    )

    # If environment variable 'LOG_LEVEL' is set to 'DEBUG', enable the DebugLogMiddleware
    if os.environ.get("LOG_LEVEL", None) == "DEBUG":
        app.wsgi_app = DebugLogMiddleware(app=app.wsgi_app)

    return app
