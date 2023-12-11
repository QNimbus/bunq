# rules.py

# Standard library imports
import re
import json
from typing import Union

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Local application/library imports
from . import logger
from libs.exceptions import RuleProcessingError
from schema.rules_model import Action, PropertyRuleType, BalanceRuleType, RuleCondition, RuleModel, RuleGroup, RuleThatActsOnAProperty, RuleThatActsOnBalance
from schema.callback_model import (
    EventType,
    PaymentType,
    RequestInquiryType,
    RequestResponseType,
    MasterCardActionType,
)


# Load rules from JSON file and validate against schema
def load_rules(schema: any, rules_path: str) -> list[RuleGroup]:
    """
    Loads the rules from the given JSON file and validates against the schema.

    Args:
        schema (dict): The JSON schema against which to validate the rules.
        rules_path (str): The path to the JSON file containing the rules.

    Returns:
        RootModel: The rules model.

    Raises:
        RuleProcessingError: If an error occurs in loading or validating the rules.
    """
    try:
        with open(rules_path, encoding="utf-8") as rules_file:
            rules = json.load(rules_file)

        validate(instance=rules, schema=schema)

        return TypeAdapter(RuleModel).validate_python(rules).root

    except (PermissionError, FileNotFoundError) as error:
        raise RuleProcessingError(f"Error loading rules: {error}") from error
    except json.JSONDecodeError as error:
        raise RuleProcessingError(f"Error decoding rules: {error}") from error
    except ValidationError as error:
        raise RuleProcessingError(f"Error validating rules: {error}") from error


def check_rule(
    data: PaymentType | RequestInquiryType | RequestResponseType | MasterCardActionType,
    rule: RuleThatActsOnAProperty | RuleThatActsOnBalance,
) -> bool:  # pylint: disable=too-many-locals
    """
    Checks if a given rule matches the given payment data.

    Args:
        data (PaymentType | RequestInquiryType | RequestResponseType | MasterCardActionType): The payment data to be checked.
        rule (RuleThatActsOnAProperty | RuleThatActsOnBalance): The rule definition to be applied.

    Returns:
        bool: True if the rule matches, False otherwise.

    Raises:
        RuleProcessingError: If an error occurs during rule processing.
    """
    try:
        if isinstance(rule, RuleThatActsOnAProperty):
            rule_type = rule.type
            rule_value = rule.value
            rule_case_sensitive = rule.case_sensitive
            rule_flags = re.IGNORECASE if not rule_case_sensitive else 0
            property_value = get_nested_property(data.model_dump(), rule.property)

            # Convert rule value to lowercase if rule is not case sensitive
            if rule_type != PropertyRuleType.REGEX and isinstance(property_value, str):
                if not rule_case_sensitive:
                    property_value = property_value.strip().lower()
                else:
                    property_value = property_value.strip()

            if rule_type != PropertyRuleType.REGEX and isinstance(rule_value, str):
                if not rule_case_sensitive:
                    rule_value = rule_value.strip().lower()
                else:
                    rule_value = rule_value.strip()

            if rule_type != PropertyRuleType.REGEX and isinstance(rule_value, list) and all(isinstance(item, str) for item in rule_value):
                if not rule_case_sensitive:
                    rule_value = [item.strip().lower() for item in rule_value]
                else:
                    rule_value = [item.strip() for item in rule_value]

        elif isinstance(rule, RuleThatActsOnBalance):
            rule_type = rule.type
            rule_value = float(rule.value) if hasattr(rule, "value") and rule.value is not None else None
        else:
            raise ValueError(f"Unknown rule type: {rule}")

        def regex_match():
            if property_value and rule_value:
                if isinstance(rule_value, str):
                    value = [rule_value]
                else:
                    value = rule_value

            return any(re.fullmatch(pattern=v, string=property_value or "", flags=rule_flags) for v in value)

        def is_empty():
            return not property_value

        def is_not_empty():
            return bool(property_value)

        def is_negative():
            return float(property_value) < 0

        def is_positive():
            return float(property_value) > 0

        def contains():
            if property_value and rule_value:
                if isinstance(rule_value, str):
                    value = [rule_value]
                else:
                    value = rule_value

                return any(v in property_value for v in value)
            return False

        def does_not_contain():
            if property_value and rule_value:
                if isinstance(rule_value, str):
                    value = [rule_value]
                else:
                    value = rule_value

                return all(v not in property_value for v in value)
            return False

        def equals():
            if property_value and rule_value:
                if isinstance(rule_value, str):
                    value = [rule_value]
                else:
                    value = rule_value

                return any(v == property_value for v in value)
            return False

        def does_not_equal():
            if property_value and rule_value:
                if isinstance(rule_value, str):
                    value = [rule_value]
                else:
                    value = rule_value

                return all(v != property_value for v in value)
            return False

        def balance_decreased(by: float = 0):
            same_currency = data.amount.currency == data.balance_after_mutation.currency
            balance_before_mutation = float(data.balance_after_mutation.value) - float(data.amount.value)
            return same_currency and float(data.balance_after_mutation.value) <= (balance_before_mutation - by)

        def balance_increased(by: float = 0):
            same_currency = data.amount.currency == data.balance_after_mutation.currency
            balance_before_mutation = float(data.balance_after_mutation.value) - float(data.amount.value)
            return same_currency and float(data.balance_after_mutation.value) >= (balance_before_mutation + by)

        rule_checks = {
            PropertyRuleType.REGEX: regex_match,
            PropertyRuleType.IS_EMPTY: is_empty,
            PropertyRuleType.IS_NOT_EMPTY: is_not_empty,
            PropertyRuleType.IS_NEGATIVE: is_negative,
            PropertyRuleType.IS_POSITIVE: is_positive,
            PropertyRuleType.CONTAINS: contains,
            PropertyRuleType.DOES_NOT_CONTAIN: does_not_contain,
            PropertyRuleType.EQUALS: equals,
            PropertyRuleType.DOES_NOT_EQUAL: does_not_equal,
            BalanceRuleType.BALANCE_DECREASED: balance_decreased,
            BalanceRuleType.BALANCE_INCREASED: balance_increased,
            BalanceRuleType.BALANCE_DECREASED_BY: lambda: balance_decreased(by=rule_value),
            BalanceRuleType.BALANCE_INCREASED_BY: lambda: balance_increased(by=rule_value),
        }

        return rule_checks[rule_type]()

    except Exception as error:  # pylint: disable=broad-except
        raise RuleProcessingError(f"Error processing rule: {error}") from error


def process_rules(
    event_type: EventType,
    data: PaymentType | RequestInquiryType | RequestResponseType | MasterCardActionType,
    rules: RuleModel,
) -> (bool, Action, str):
    """
    Recursively processes a list of rules and returns a tuple containing a boolean indicating whether any of the rules matched
    and a list of all the matched rules.

    Args:
        data: The data to check against the rules.
        rules: The list of rules to process.

    Returns:
        tuple: A tuple containing a boolean indicating whether any of the rules matched, a list of all the matched rules, and a list of all the non-matched rules.
    """
    result = False
    action: Action = None
    rule_name: str = None

    def process_and_capture(rule_or_rulegroup: Union[Union[RuleThatActsOnAProperty, RuleThatActsOnBalance], RuleGroup]) -> bool:
        if isinstance(rule_or_rulegroup, Union[RuleThatActsOnAProperty, RuleThatActsOnBalance]):
            rule = rule_or_rulegroup
            result = check_rule(data, rule)

            return result

        if isinstance(rule_or_rulegroup, RuleGroup):
            rules = rule_or_rulegroup
            if rules.condition == RuleCondition.ANY:
                result = any(process_and_capture(sub_rule) for sub_rule in rules.rules)
            elif rules.condition == RuleCondition.ALL:
                result = all(process_and_capture(sub_rule) for sub_rule in rules.rules)
            elif rules.condition == RuleCondition.NONE:
                results = [process_and_capture(sub_rule) for sub_rule in rules.rules]
                result = not any(results)
            else:
                raise ValueError(f"Unknown condition: {rules.condition}")

            return result

        raise ValueError(f"Unknown rule type: {rule_or_rulegroup}")

    try:
        for rule_root in rules:
            # Get 'action' from rules
            action = rule_root.action

            # FIXME: Somehow 'if event_type in rule.action.events' doesn't work. This is a workaround
            if any(event_type.value == event.value for event in action.events):
                result = process_and_capture(rule_root.rule)
                if result:
                    rule_name = rule_root.name
                    break

    except Exception as error:  # pylint: disable=broad-except
        logger.error(f"Error processing rules: {error}")

    return result, action, rule_name


def get_nested_property(data: dict, property_name: str) -> any:
    """
    Retrieves the value of a nested property within a dictionary using dot notation.

    Args:
        data (PaymentType): The dictionary from which to retrieve the value.
        property_name (str): The nested property name in dot notation (e.g., 'a.b.c').

    Returns:
        any: The value of the nested property, or None if not found.

    Raises:
        RuleProcessingError: If any error occurs in retrieving the property.
    """
    try:
        for name in property_name.split("."):
            data = data.get(name)
            if data is None:
                return None
        return data
    except Exception as error:
        raise RuleProcessingError(f"Error accessing property '{property_name}': {error}") from error
