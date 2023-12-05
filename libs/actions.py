# actions.py

# Standard library imports
import os
import math

# Third-party imports
# ...

# Local application/library imports
from libs.logger import setup_logger
from libs.rules import get_nested_property
from libs.bunq_lib import BunqLib, CounterParty, RequestInquiryOptions, PaymentOptions
from schema.rules_model import ForwardPaymentActionData, CreateRequestActionData, ForwardRemainingBalanceActionData
from schema.callback_model import PaymentType

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


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
    accounts = {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}

    description = payment.description
    amount = float(payment.amount.value)
    counterparty = CounterParty(
        name=action.forward_payment_to.name,
        iban=action.forward_payment_to.iban,
    )
    account = f"{accounts[payment.monetary_account_id].display_name}|{accounts[payment.monetary_account_id].description}"

    # Create a list comprehension of all the IBAN numbers of the accounts that are allowed to receive the remaining balance.
    own_accounts = [alias.value for id in accounts.keys() for alias in accounts[id].alias if hasattr(alias, "type_") and alias.type_ == "IBAN"]

    if not action.allow_third_party_accounts and action.forward_payment_to.iban not in own_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} is not allowed to third party accounts ({action.forward_payment_to.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} -> {account} - {description}"

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
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_PAYMENT::{payment.id} Calling 'bunq_lib.make_payment' with {request_data}")


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
    accounts = {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}

    description = payment.description
    amount = float(payment.amount.value)
    counterparty = CounterParty(
        name=action.forward_payment_to.name,
        iban=action.forward_payment_to.iban,
    )

    # Create a list comprehension of all the IBAN numbers of the accounts that are allowed to receive the remaining balance.
    own_accounts = [alias.value for id in accounts.keys() for alias in accounts[id].alias if hasattr(alias, "type_") and alias.type_ == "IBAN"]

    if not action.allow_third_party_accounts and action.forward_payment_to.iban not in own_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} is not allowed to third party accounts ({action.forward_payment_to.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} -> {action.forward_payment_to.name} - {description}"

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
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_INCOMING_PAYMENT::{payment.id} Calling 'bunq_lib.make_payment' with {request_data}")


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
    accounts = {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}

    description = payment.description
    amount = float(payment.amount.value) * -1
    counterparty = CounterParty(name=action.request_from.name, iban=action.request_from.iban)
    request_account = f"{accounts[payment.monetary_account_id].display_name}|{accounts[payment.monetary_account_id].description}"

    # Create a list comprehension of all the IBAN numbers of the accounts that are allowed to receive the remaining balance.
    own_accounts = [alias.value for id in accounts.keys() for alias in accounts[id].alias if hasattr(alias, "type_") and alias.type_ == "IBAN"]

    if action.ignore_own_accounts and payment.counterparty_alias.iban in own_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} is not allowed for own accounts ({payment.counterparty_alias.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] REQUEST_FROM_PAYMENT::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} -> {request_account} - {description}"

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


def action_forward_remaining_balance(bunq_lib: BunqLib, action: ForwardRemainingBalanceActionData, payment: PaymentType, dry_run: bool = False) -> None:
    """
    Perform a forward remaining balance action.

    Args:
        bunq_lib (BunqLib): The BunqLib instance used for making payments.
        action (ForwardRemainingBalanceActionData): The data for the forward remaining balance action.
        payment (PaymentType): The payment to be forwarded.

    Returns:
        None
    """
    # Get own accounts
    accounts = {account.id_: account for account in bunq_lib.get_all_accounts(only_active=True)}

    # Calculate the remaining balance to be forwarded. Round downwards
    amount = math.floor((float(payment.balance_after_mutation.value) - float(payment.amount.value)) * 100) / 100

    description = payment.description
    request_account = f"{accounts[payment.monetary_account_id].display_name}|{accounts[payment.monetary_account_id].description}"
    counterparty = CounterParty(
        name=action.forward_remaining_balance_to.name,
        iban=action.forward_remaining_balance_to.iban,
    )

    # Create a list comprehension of all the IBAN numbers of the accounts that are allowed to receive the remaining balance.
    allowed_accounts = [alias.value for id in accounts.keys() for alias in accounts[id].alias if hasattr(alias, "type_") and alias.type_ == "IBAN"]

    if action.forward_remaining_balance_to.iban not in allowed_accounts and not action.allow_third_party_accounts:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_REMAINING_BALANCE::{payment.id} is not allowed to third party accounts ({action.forward_remaining_balance_to.iban})")
        return

    if amount <= 0:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_REMAINING_BALANCE::{payment.id} requires amount > 0 ({amount})")
        return

    if action.description is not None:
        description = f"{action.description} -> {request_account} - {description}"

    request_data = {
        "amount": amount,
        "counterparty": counterparty,
        "monetary_account_id": payment.monetary_account_id,
        "options": PaymentOptions(description=description),
    }

    if not dry_run:
        bunq_lib.make_payment(**request_data)
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_REMAINING_BALANCE::{payment.id} {payment.monetary_account_id} -> {description}")
    else:
        logger.info(f"[/callback/{bunq_lib.user_id}] FORWARD_REMAINING_BALANCE::{payment.id} Calling 'bunq_lib.make_request' with {request_data}")
