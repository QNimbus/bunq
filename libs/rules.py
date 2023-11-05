# rules.py

# Standard library imports
import os
import re
import json
from typing import Union

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Local application/library imports
from libs.log import setup_logger
from libs.exceptions import RuleProcessingError
from schema.callback_model import Payment
from schema.rules_model import RuleType, Condition, Rule, Rules, RuleGroup

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


# Load rules from JSON file and validate against schema
def load_rules(schema: any, rules_path: str) -> list[Union[Rule, RuleGroup]]:
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

        return TypeAdapter(Rules).validate_python(rules).root

    except ValidationError as error:
        # Return the error message and details about the failed validation
        error_details = {
            "message": str(error.message),
            "validator": error.validator,
            "validator_value": error.validator_value,
            "path": list(error.path),
            "schema_path": list(error.schema_path),
        }

        logger.debug(
            f"Error validating rules:':\n\n{json.dumps(error_details, indent=2)}"
        )

        raise RuleProcessingError(f"Error validating rules: {error}") from error
    except Exception as error:
        raise RuleProcessingError(f"Error loading rules: {error}") from error


def check_rule(data: Payment, rule: Rule) -> bool:  # pylint: disable=too-many-locals
    """
    Checks if a given rule matches the given payment data.

    Args:
        data (Payment): Payment data.
        rule (Rule): Rule definition.

    Returns:
        bool: True if rule matches, False otherwise.

    Raises:
        RuleProcessingError: If an error occurs during rule processing.
    """
    try:
        rule_type = rule.type
        rule_value = rule.value
        property_value = get_nested_property(data.model_dump(), rule.property)

        def regex_match():
            return re.fullmatch(rule_value, property_value or "") is not None

        def is_empty():
            return not property_value

        def is_not_empty():
            return bool(property_value)

        def is_negative():
            return float(property_value) < 0

        def is_positive():
            return float(property_value) > 0

        def contains():
            if property_value:
                low_prop_val = property_value.strip().lower()
                return any(val.strip().lower() in low_prop_val for val in rule_value)
            return False

        def does_not_contain():
            if property_value:
                low_prop_val = property_value.strip().lower()
                return all(
                    val.strip().lower() not in low_prop_val for val in rule_value
                )
            return True

        def equals():
            return property_value == rule_value

        def does_not_equal():
            return property_value != rule_value

        rule_checks = {
            RuleType.REGEX: regex_match,
            RuleType.IS_EMPTY: is_empty,
            RuleType.IS_NOT_EMPTY: is_not_empty,
            RuleType.IS_NEGATIVE: is_negative,
            RuleType.IS_POSITIVE: is_positive,
            RuleType.CONTAINS: contains,
            RuleType.DOES_NOT_CONTAIN: does_not_contain,
            RuleType.EQUALS: equals,
            RuleType.DOES_NOT_EQUAL: does_not_equal,
        }

        return rule_checks[rule_type]()

    except Exception as error:  # pylint: disable=broad-except
        # raise RuleProcessingError(f"Error processing rule: {error}") from error
        logger.debug(f"Error processing rule: {error}")
        return False


def process_rules(
    data: Payment, rules: list[Rule | RuleGroup]
) -> (bool, list[str], list[str]):
    """
    Recursively processes a list of rules and returns a tuple containing a boolean indicating whether any of the rules matched
    and a list of all the matched rules.

    Args:
        data: The data to check against the rules.
        rules: The list of rules to process.

    Returns:
        tuple: A tuple containing a boolean indicating whether any of the rules matched, a list of all the matched rules, and a list of all the non-matched rules.
    """
    matching_rules: list[tuple[str, str]] = []
    non_matching_rules: list[tuple[str, str]] = []

    def process_and_capture(rule_or_rulegroup: Rule | RuleGroup) -> bool:
        if isinstance(rule_or_rulegroup, Rule):
            rule = rule_or_rulegroup
            result = check_rule(data, rule)
            if result:
                matching_rules.append(("Rule", rule.name))
            else:
                non_matching_rules.append(("Rule", rule.name))
            return result

        if isinstance(rule_or_rulegroup, RuleGroup):
            rules = rule_or_rulegroup
            if rules.condition == Condition.ANY:
                result = any(process_and_capture(sub_rule) for sub_rule in rules.rules)
            elif rules.condition == Condition.ALL:
                result = all(process_and_capture(sub_rule) for sub_rule in rules.rules)
            elif rules.condition == Condition.NONE:
                results = [process_and_capture(sub_rule) for sub_rule in rules.rules]
                result = not any(results)
            else:
                raise ValueError(f"Unknown condition: {rules.condition}")

            if result:
                if rules.name:
                    matching_rules.append(("RuleGroup", rules.name))
            else:
                if rules.name:
                    non_matching_rules.append(("RuleGroup", rules.name))

            return result

        raise ValueError(f"Unknown rule type: {rule_or_rulegroup}")

    for rule in rules:
        result = process_and_capture(rule)

    return result, matching_rules, non_matching_rules


def get_nested_property(data: dict, property_name: str) -> any:
    """
    Retrieves the value of a nested property within a dictionary using dot notation.

    Args:
        data (Payment): The dictionary from which to retrieve the value.
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
        raise RuleProcessingError(
            f"Error accessing property '{property_name}': {error}"
        ) from error
