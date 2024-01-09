# config_loaders.py

# Standard library imports
import json
from pathlib import Path

# Third-party imports
from flask import Flask

# Local application/library imports
from schema.rules_model import RuleModel
from libs.bunq_lib import BunqLib
from libs.rules import load_rules_from_file
from libs.exceptions import RuleProcessingError, BunqLibError

# Import logger
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


def load_rules(app: Flask, rules: Path, rules_schema: dict) -> None:
    """
    Load rules from the specified directory and store them in the Flask app's configuration.

    Args:
        app (Flask): The Flask application.
        rules_dir (Path): The directory containing the rules files.
        rules_schema (dict): The schema to validate the rules against.

    Raises:
        RuleProcessingError: If there is an error processing the rules.

    Returns:
        None
    """
    try:
        rules_collection: RuleModel = app.config.get("RULES", {})

        # Test if rules_dir points to a directory or a file:
        if rules.is_file():
            rules_collection[rules.name] = load_rules_from_file(schema=rules_schema, rules_file_path=rules)
            logger.info(f"Loaded rules from {rules}")

        if rules.is_dir():
            for file in rules.glob("*.rules.json"):
                rules_file = rules / file
                rules_collection[file.name] = load_rules_from_file(schema=rules_schema, rules_file_path=rules_file)
                logger.info(f"Loaded rules from {rules_file}")

        app.config["RULES"] = rules_collection

    except RuleProcessingError as error:
        logger.error(error)


def load_configs(app: Flask, conf_dir: Path) -> None:
    """
    Load configurations from JSON files and store them in the Flask app's configuration.

    Args:
        app (Flask): The Flask application.
        conf_dir (Path): The directory containing the configuration files.

    Raises:
        BunqLibError: If there is an error loading the configuration.

    Returns:
        None
    """
    try:
        bunq_configs: dict[str, BunqLib] = {}
        for file in conf_dir.glob("*.conf"):
            conf_file = conf_dir / file
            bunq_lib = BunqLib(production_mode=True, config_file=conf_file)
            bunq_configs[bunq_lib.user_id] = bunq_lib
            logger.info(f"Initialized BunqLib for user '{bunq_lib.user.display_name}' with config file: {conf_file}")

        app.config["BUNQ_CONFIGS"] = bunq_configs

    except BunqLibError as error:
        logger.error(error)


def load_schemas(app: Flask, schema_dir: Path) -> None:
    """
    Load schemas from JSON files and store them in the Flask app's configuration.

    Args:
        app (Flask): The Flask application.
        schema_dir (Path): The directory containing the schema files.

    Raises:
        FileNotFoundError: If the schema file does not exist.
        PermissionError: If the schema file cannot be read.

    Returns:
        None
    """
    schemas = ["rules", "callback"]

    for schema_name in schemas:
        try:
            schema_file = schema_dir / f"{schema_name}.schema.json"
            with open(schema_file, "r", encoding="utf-8") as file:
                rules_schema = json.load(file)
                logger.info(f"Loaded rules schema from {schema_file}")

            key = schema_name.upper() + "_SCHEMA"
            app.config[key] = rules_schema

        except (FileNotFoundError, PermissionError) as error:
            logger.error(error)
