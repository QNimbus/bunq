# payment.py

# Standard library imports
from threading import Lock

# Third-party imports
from typing import Optional
from flask import current_app
from pydantic import TypeAdapter
from flask.ctx import AppContext

# Local application/library imports
from libs.bunq_lib import BunqLib, Utilites
from libs.rules import process_rules
from libs.redis_wrapper import RedisWrapper
from libs.actions import action_request_from_expense, action_transfer_remaining_balance, action_transfer_incoming_payment
from schema.callback_model import CallbackModel, EventType, PaymentType
from schema.rules_model import RuleModel, TransferRemainingBalanceActionData, TransferIncomingPaymentActionData, RequestFromExpenseActionData, ActionType
from . import logger


# Setup lock for thread synchronization inside the 'process_payment' function
lock = Lock()


def _validate_payment_data(callback_data: CallbackModel) -> PaymentType:
    """
    Validates the payment data received from the callback.

    Args:
        callback_data (CallbackModel): The callback data containing the payment information.

    Returns:
        PaymentType: The validated payment data.

    """
    return TypeAdapter(PaymentType).validate_python(callback_data.NotificationUrl.object.root.Payment)


def _process_rule_collection(rules: list[RuleModel], event_type: EventType, payment_data: PaymentType, user_id: str) -> tuple[bool, Optional[ActionType]]:
    """
    Process a rule based on the given parameters.

    Args:
        rules (list): The list of rules to be processed.
        event_type (EventType): The type of event.
        payment_data (PaymentType): The payment data.
        user_id (str): The user ID.

    Returns:
        tuple: A tuple containing a boolean indicating the success of the rule processing and the action to be taken.
    """
    success, action, rule_name = process_rules(event_type=event_type, data=payment_data, rules=rules)

    # If the rule is not successful or no action is found, return False
    if not success or action is None:
        return False, None

    logger.info(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} Payment matches '{rule_name}::{action.type.value}'")

    # Remove the payment id from the processed payments list if the action is a dummy action or if the dry_run flag is set to True
    if action.dry_run or action.type == ActionType.DUMMY:
        RedisWrapper.unregister_payment(user_id=user_id, payment_id=payment_data.id)

    return True, action


def process_payment(*, app_context: AppContext, user_id: int, request_id: str, event_type: EventType, callback_data: CallbackModel) -> None:
    """
    Process a payment created notification and create a request in Bunq if the payment matches the rules.

    Args:
        app_context (AppContext): The Flask application context.
        user_id (int): The ID of the user.
        request_id (str): The ID of the request.
        event_type (EventType): The type of event.
        callback_data (CallbackModel): The notification data.

    Returns:
        None

    Raises:
        RuntimeError: If the request ID is not set in the request.
    """
    try:
        app_context.push()

        # Get request_log from Redis. If it does not exist, throw an error
        current_request = RedisWrapper.get_request_data(request_id=request_id)

        if current_request is None:
            raise RuntimeError(f"Request id not found in request_log: {request_id}")

        # Declare 'success' boolean and 'action' variable
        success = False
        action = None

        payment_data = _validate_payment_data(callback_data)

        # Get or initialize the processed payments list
        processed_payments = RedisWrapper.get_processed_payments_for_user(user_id=user_id)

        # Check if the payment id is already in the processed payments list for the user
        if payment_data.id in processed_payments:
            logger.info(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} Payment already processed")
            return

        # Add the payment id to the processed payments list
        RedisWrapper.register_payment(user_id=user_id, payment_id=payment_data.id)

        # Get the rules from the app session
        rule_collections: dict[str, RuleModel] = current_app.config.get("RULES", {})

        for rules in rule_collections.values():
            success, action = _process_rule_collection(rules, event_type, payment_data, user_id)
            if success:
                break

        bunq_lib: BunqLib = current_app.config["BUNQ_CONFIGS"][user_id]
        user = bunq_lib.user
        monetary_account_id = payment_data.monetary_account_id

        # Update the request log with the success of the request
        current_request["event"] = event_type.value
        current_request["success"] = success
        current_request["action"] = action.type.value if action is not None else None
        current_request["display_name"] = user.display_name
        RedisWrapper.set_request_data(request_id=request_id, data=current_request)

        if not success:
            logger.info(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} Payment did not match any rules")
            return

        # Create array of monetary account ids from accounts list
        try:
            accounts = Utilites.get_accounts_by_monetary_account_id(bunq_lib)
        except Exception as error:  # pylint: disable=broad-except
            logger.error(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} Failed to retrieve accounts: {error}")
            return

        if action.type.value == "DUMMY":
            logger.debug(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} Dummy action")
            logger.debug(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} account: {payment_data.alias.iban} ({payment_data.alias.display_name})")
            logger.debug(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} counterparty: {payment_data.counterparty_alias.iban} ({payment_data.counterparty_alias.display_name})")
            logger.debug(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} amount: {payment_data.amount.value} {payment_data.amount.currency}")
            logger.debug(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} description: {payment_data.description}")

        if action.type == ActionType.REQUEST_FROM_EXPENSE:
            # If the monetary account id is found in the accounts list, perform action
            if monetary_account_id in accounts.keys():
                request_from_expense_action_data = TypeAdapter(RequestFromExpenseActionData).validate_python(action.data)

                action_request_from_expense(bunq_lib=bunq_lib, action=request_from_expense_action_data, payment=payment_data, dry_run=action.dry_run)

        if action.type == ActionType.TRANSFER_INCOMING_PAYMENT:
            # If the monetary account id is found in the accounts list, perform action
            if monetary_account_id in accounts.keys():
                transfer_incoming_payment_action_data = TypeAdapter(TransferIncomingPaymentActionData).validate_python(action.data)

                action_transfer_incoming_payment(bunq_lib=bunq_lib, action=transfer_incoming_payment_action_data, payment=payment_data, dry_run=action.dry_run)

        if action.type == ActionType.TRANSFER_REMAINING_BALANCE:
            # If the monetary account id is found in the accounts list, perform action
            if monetary_account_id in accounts.keys():
                transfer_remaining_balance_action_data = TypeAdapter(TransferRemainingBalanceActionData).validate_python(action.data)

                action_transfer_remaining_balance(bunq_lib=bunq_lib, action=transfer_remaining_balance_action_data, payment=payment_data, dry_run=action.dry_run)

    except Exception as error:  # pylint: disable=broad-except
        logger.error(f"[/callback/{user_id}] {event_type.value}::{payment_data.id} {error}")
