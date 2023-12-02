# server.py

# Standard library imports
import os
import json
from typing import Union

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, jsonify, request, current_app

# Local application/library imports
from libs.bunq_lib import BunqLib, CounterParty, MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings, RequestInquiryOptions, PaymentOptions
from libs.redis_wrapper import RedisWrapper
from libs.log import setup_logger, setup_logger_with_rotating_file_handler
from libs.decorator import route, routes
from libs.rules import process_rules, load_rules, get_nested_property
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware
from schema.rules_model import Rules, Action, ForwardPaymentActionData, CreateRequestActionData, ForwardRemainingBalanceActionData
from schema.callback_model import CallbackModel, EventType, PaymentType


# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))
callback_logger = setup_logger_with_rotating_file_handler(
    "callback",
    log_level="INFO",
    filename="logs/callback.log",
    max_bytes=100 * 1024 * 1024,
    backup_count=5,
)
failed_callback_logger = setup_logger_with_rotating_file_handler(
    "fail",
    log_level="INFO",
    filename="logs/fail.log",
    max_bytes=100 * 1024 * 1024,
    backup_count=5,
)


def get_all_accounts(
    bunq_lib: BunqLib,
) -> dict[int, Union[MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings]]:
    """
    Retrieve all active accounts from the BunqLib instance.

    Args:
        bunq_lib (BunqLib): The BunqLib instance.

    Returns:
        dict[int, Union[MonetaryAccountBank, MonetaryAccountJoint, MonetaryAccountSavings]]:
        A dictionary of accounts with the account id as key.
    """
    return {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}


def process_payment(
    bunq_lib: BunqLib,
    event_type: EventType,
    callback_data: CallbackModel,
) -> None:
    """
    Process a payment created notification and create a request in Bunq if the payment matches the rules.

    Args:
        bunq_lib (BunqLib): The BunqLib instance used for making payments.
        event_type (EventType): The type of event.
        callback_data (CallbackModel): The notification data.

    Returns:
        None
    """
    payment_data = TypeAdapter(PaymentType).validate_python(callback_data.NotificationUrl.object.root.Payment)

    # Get the rules from the app session
    rule_collections: dict[str, Rules] = current_app.config.get("RULES", {})

    # Get or initialize the processed payments list
    processed_payments: dict[int, list[str]] = RedisWrapper.get_secure("processed_payments") or {}
    processed_payments.setdefault(bunq_lib.user_id, [])

    # Check if the payment id is already in the processed payments list for the user
    if payment_data.id in processed_payments[bunq_lib.user_id]:
        logger.info(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} Payment already processed")
        return

    processed_payments[bunq_lib.user_id].append(payment_data.id)

    # Declare 'success' bool to check if any of the rules are successful
    success = False

    for rules_file, rules in rule_collections.items():
        logger.debug(f"Processing rule: {rules_file}")

        success, action, rule_name = process_rules(event_type=event_type, data=payment_data, rules=rules)

        # If the rule is not successful or no action is found, continue to the next rule
        if not success or action is None:
            continue

        # Register the processed payments list in Redis
        if not action.dry_run or action.type.value == "DUMMY":
            RedisWrapper.set_secure("processed_payments", processed_payments)

        logger.info(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} Payment matches '{rules_file}::{rule_name}'")

        if action.type.value == "DUMMY":
            logger.debug(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} Dummy action")
            logger.debug(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} account: {payment_data.alias.iban} ({payment_data.alias.display_name})")
            logger.debug(
                f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} counterparty: {payment_data.counterparty_alias.iban} ({payment_data.counterparty_alias.display_name})"
            )
            logger.debug(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} amount: {payment_data.amount.value} {payment_data.amount.currency}")
            logger.debug(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} description: {payment_data.description}")

            break

        if action.type.value in ("FORWARD_PAYMENT", "FORWARD_INCOMING_PAYMENT"):
            monetary_account_id = payment_data.monetary_account_id

            # Create array of monetary account ids from accounts list
            accounts = get_all_accounts(bunq_lib)

            # If the monetary account id is found in the accounts list, create a request
            if monetary_account_id in accounts.keys():
                forward_payment_action_data = TypeAdapter(ForwardPaymentActionData).validate_python(action.data)

                if action.type.value == "FORWARD_PAYMENT":
                    action_forward_payment(bunq_lib=bunq_lib, action=forward_payment_action_data, payment=payment_data, dry_run=action.dry_run)
                elif action.type.value == "FORWARD_INCOMING_PAYMENT":
                    action_forward_incoming_payment(bunq_lib=bunq_lib, action=forward_payment_action_data, payment=payment_data, dry_run=action.dry_run)

            break

        if action.type.value == "REQUEST_FROM_PAYMENT":
            monetary_account_id = payment_data.monetary_account_id

            # Create array of monetary account ids from accounts list
            accounts = get_all_accounts(bunq_lib)

            # If the monetary account id is found in the accounts list, create a request
            if monetary_account_id in accounts.keys():
                create_request_action_data = TypeAdapter(CreateRequestActionData).validate_python(action.data)

                action_request_from_payment(bunq_lib=bunq_lib, action=create_request_action_data, payment=payment_data, dry_run=action.dry_run)

            break

        if action.type.value == "FORWARD_REMAINING_BALANCE":
            monetary_account_id = payment_data.monetary_account_id

            # Create array of monetary account ids from accounts list
            accounts = get_all_accounts(bunq_lib)

            # If the monetary account id is found in the accounts list, create a request
            if monetary_account_id in accounts.keys():
                forward_remaining_balance_action_data = TypeAdapter(ForwardRemainingBalanceActionData).validate_python(action.data)

            
            break

    if not success:
        logger.info(f"[/callback/{bunq_lib.user_id}] {event_type.value}::{payment_data.id} Payment did not match any rules")


def action_forward_payment(bunq_lib: BunqLib, action: ForwardPaymentActionData, payment: PaymentType, dry_run: bool = False) -> None:
    """
    Perform a forward payment action.

    Args:
        bunq_lib (BunqLib): The BunqLib instance used for making payments.
        action (ForwardPaymentActionData): The data for the forward payment action.
        payment (PaymentType): The payment to be forwarded.

    Returns:
        None
    """
    # Get own accounts
    accounts = get_all_accounts(bunq_lib)

    description = payment.description
    counterparty = CounterParty(
        name=action.forward_payment_to.name,
        iban=action.forward_payment_to.iban,
    )
    amount = float(get_nested_property(payment.model_dump(), action.amount_value_property)) * -1

    if payment.monetary_account_id not in accounts.keys() and not action.allow_third_party_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} is not allowed to third party accounts ({action.forward_payment_to.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} - {description}"

    logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} {payment.monetary_account_id} -> {description}")

    request_data = {
        "amount": amount,
        "counterparty": counterparty,
        "monetary_account_id": payment.monetary_account_id,
        "options": PaymentOptions(description=description),
    }

    if not dry_run:
        bunq_lib.make_payment(**request_data)
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} {payment.monetary_account_id} -> {description}")
    else:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} Calling 'bunq_lib.make_request' with {request_data}")


def action_forward_incoming_payment(bunq_lib: BunqLib, action: ForwardPaymentActionData, payment: PaymentType, dry_run: bool = False) -> None:
    """
    Perform the action to forward an incoming payment.

    Args:
        bunq_lib (BunqLib): The BunqLib instance used for making payments.
        action (ForwardPaymentActionData): The data for the forward payment action.
        payment (PaymentType): The incoming payment to be forwarded.

    Returns:
        None
    """
    # Get own accounts
    accounts = get_all_accounts(bunq_lib)

    description = payment.description
    counterparty = CounterParty(
        name=action.forward_payment_to.name,
        iban=action.forward_payment_to.iban,
    )
    amount = float(get_nested_property(payment.model_dump(), action.amount_value_property))

    if payment.monetary_account_id not in accounts.keys() and not action.allow_third_party_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} is not allowed to third party accounts ({action.forward_payment_to.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} - {description}"

    request_data = {
        "amount": amount,
        "counterparty": counterparty,
        "monetary_account_id": payment.monetary_account_id,
        "options": PaymentOptions(description=description),
    }

    if not dry_run:
        bunq_lib.make_payment(**request_data)
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} {payment.monetary_account_id} -> {description}")
    else:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} Calling 'bunq_lib.make_request' with {request_data}")


def action_request_from_payment(bunq_lib: BunqLib, action: CreateRequestActionData, payment: PaymentType, dry_run: bool = False) -> None:
    """
    Perform a request from payment action.

    Args:
        bunq_lib (BunqLib): The BunqLib instance.
        action (CreateRequestActionData): The action data for creating a request.
        payment (PaymentType): The payment data.

    Returns:
        None
    """
    # Get own accounts
    accounts = get_all_accounts(bunq_lib)

    description = payment.description
    amount = float(get_nested_property(payment.model_dump(), action.amount_value_property)) * -1
    counterparty = CounterParty(name=action.request_from.name, iban=action.request_from.iban)
    request_account = f"{accounts[payment.monetary_account_id].display_name}|{accounts[payment.monetary_account_id].description}"

    if action.ignore_own_accounts and payment.counterparty_alias.iban in accounts.keys():
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} is not allowed for own accounts ({accounts[payment.counterparty_alias.iban].description})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} --> {request_account} - {description}"

    request_data = {
        "amount": amount,
        "counterparty": counterparty,
        "monetary_account_id": payment.monetary_account_id,
        "options": RequestInquiryOptions(description=description),
    }

    if not dry_run:
        bunq_lib.make_request(**request_data)
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} {payment.monetary_account_id} -> {description}")
    else:
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} Calling 'bunq_lib.make_request' with {request_data}")


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


@route("/callback/<int:user_id>", methods=["POST"])
def callback(user_id: int):
    """
    Handles callbacks from another application via HTTP POST.

    Parameters:
    - user (str): The name of the user.

    Returns:
    - JSON response with a success message if the request is valid and from an allowed IP.
    - JSON response with an error message if the request is invalid or the schema does not match.
    """
    # Return 400 if the request is not JSON
    if not request.is_json:
        logger.info(f"[/callback/{user_id}] Invalid request: {request}")
        return jsonify({"message": "Invalid request"}), 400

    # Fetch all available user ids from the app session
    keys = current_app.config["BUNQ_CONFIGS"].keys() if "BUNQ_CONFIGS" in current_app.config else []

    if user_id not in keys:
        logger.info(f"[/callback/{user_id}] Invalid user id: {user_id}")
        return jsonify({"message": "Invalid user id"}), 400

    try:
        request_data = request.get_json()
        request_schema = current_app.config["CALLBACK_SCHEMA"]

        # Validate the request data against the schema
        validate(instance=request_data, schema=request_schema)

        # Log the json data
        callback_logger.info(json.dumps(request_data))

        callback_data = TypeAdapter(CallbackModel).validate_python(request_data)
        event_type = callback_data.NotificationUrl.event_type

        # Dictionary to simulate a switch/case structure
        switcher = {
            "PAYMENT_CREATED": process_payment,
            "PAYMENT_RECEIVED": process_payment,
            "MUTATION_CREATED": process_payment,
            "MUTATION_RECEIVED": process_payment,
            "CARD_PAYMENT_ALLOWED": None,
            "CARD_TRANSACTION_NOT_ALLOWED": None,
            "REQUEST_INQUIRY_CREATED": None,
            "REQUEST_INQUIRY_ACCEPTED": None,
            "REQUEST_INQUIRY_REJECTED": None,
            "REQUEST_RESPONSE_CREATED": None,
            "REQUEST_RESPONSE_ACCEPTED": None,
            "REQUEST_RESPONSE_REJECTED": None,
        }

        # Get the function from switcher dictionary
        handler = switcher.get(event_type.value, None)

        # Execute the handler function if it exists and pass the data object
        if handler is not None and callback_data is not None:
            handler(
                bunq_lib=current_app.config["BUNQ_CONFIGS"][user_id],
                event_type=event_type,
                callback_data=callback_data,
            )
        else:
            logger.info(f"[/callback/{user_id}] Unregistered event type {event_type.value}")

        return jsonify({"message": "Success"})
    except ValidationError:
        # Log the failed callback json data
        failed_callback_logger.info(json.dumps(request_data))

        logger.info(f"[/callback/{user_id}] Schema mismatch: {request}")

        # Return 200 to prevent Bunq callback api to retry the request
        return jsonify({"message": "Schema mismatch"}), 200


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
    bunq_configs: dict[str, BunqLib] = {}
    conf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conf/")
    for file in os.listdir(conf_dir):
        if file.endswith(".conf"):
            conf_file = os.path.join(conf_dir, file)
            bunq_lib = BunqLib(production_mode=True, config_file=conf_file)
            bunq_configs[bunq_lib.user_id] = bunq_lib
            logger.info(f"Initialized BunqLib for user '{bunq_lib.user.display_name}' with config file: {conf_file}")

    # Create the Flask application
    app = Flask(__name__)

    # Store schema in app session
    app.config["RULES"] = rules
    app.config["BUNQ_CONFIGS"] = bunq_configs
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
