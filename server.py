# server.py

# Standard library imports
import os
import json

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, jsonify, request, current_app

# Local application/library imports
# ...

# from schema import payment_model
from libs.log import setup_logger, setup_logger_with_rotating_file_handler
from libs.decorator import route, routes
from libs.rules import process_rules, load_rules
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware
from schema.callback_model import CallbackModel


# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))
callback_logger = setup_logger_with_rotating_file_handler(
    "callback",
    log_level="INFO",
    filename="data/callback.log",
    max_bytes=100 * 1024 * 1024,
    backup_count=5,
)


def process_payment_created(app: Flask, data: CallbackModel) -> None:
    """
    Process a payment created notification and create a request in Bunq if the payment matches the rules.

    Args:
        app (Flask): The Flask app instance.
        data (CallbackModel): The notification data.

    Returns:
        None
    """
    payment = data.NotificationUrl.object.Payment

    logger.debug(
        f"PAYMENT_CREATED: {payment.alias.display_name} - {payment.description} ({payment.id})"
    )

    rule_collections: dict[str, any] = app.config["RULES"]

    for rules_file, rules in rule_collections.items():
        logger.debug(f"Processing rule: {rules_file}")

        success, _matching, _non_matching = process_rules(data=payment, rules=rules)

        if success:
            logger.info(
                f"PAYMENT_CREATED: {payment.alias.display_name} - {payment.description} ({payment.id}) matches rules in {rules_file}"
            )


def process_payment_received(
    app: Flask, data: CallbackModel
) -> None:  # pylint: disable=unused-argument
    """
    Process a payment received notification and log the payment details.

    Args:
        app (Flask): The Flask application instance.
        data (CallbackModel): The notification data.

    Returns:
        None
    """
    payment = data.NotificationUrl.object.Payment
    logger.info(
        f"PAYMENT_RECEIVED: {payment.alias.display_name} - {payment.description} ({payment.id})"
    )


def process_unregistered_event(
    app: Flask, data: any
) -> None:  # pylint: disable=unused-argument
    """
    Process an unregistered event type.

    Args:
        app (Flask): The Flask application instance.
        data (any): The data associated with the unregistered event.

    Returns:
        None
    """
    logger.debug("Unregistered event type")


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
        logger.info(f"Callback data: {json.dumps(request_data)}")

        callback_data = TypeAdapter(CallbackModel).validate_python(request_data)
        event_type = callback_data.NotificationUrl.event_type

        # Dictionary to simulate a switch/case structure
        switcher = {
            "PAYMENT_CREATED": process_payment_created,
            "PAYMENT_RECEIVED": process_payment_received,
        }

        # Get the function from switcher dictionary
        case = switcher.get(event_type, process_unregistered_event)

        # Execute the function
        case(current_app, callback_data)

        return jsonify({"message": "Success"})
    except ValidationError as exc:
        # Return the error message and details about the failed validation
        error_details = {
            "message": str(exc.message),
            "validator": exc.validator,
            "validator_value": exc.validator_value,
            "path": list(exc.path),
            "schema_path": list(exc.schema_path),
        }

        # Log failed schema validation
        logger.info(f"Callback data failed validation: {json.dumps(request_data)}")

        # Debug log detailed reason for schema validation
        logger.debug(
            f"JSON schema validation failed:\n\n{json.dumps(error_details, indent=2)}"
        )

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
    rules_schema_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "schema/rules.schema.json"
    )
    with open(rules_schema_file, "r", encoding="utf-8") as file:
        rules_schema = json.load(file)

    # Load the rules from external files
    rules = {}
    rules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules/")
    for file in os.listdir(rules_dir):
        if file.endswith("rules.json"):
            rules_file = os.path.join(rules_dir, file)
            rules[file] = load_rules(schema=rules_schema, rules_path=rules_file)
            logger.info(f"Loaded rules from {rules_file}")

    # Load the callback schema from an external file
    callback_schema_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "schema/callback.schema.json"
    )
    with open(callback_schema_file, "r", encoding="utf-8") as file:
        callback_schema = json.load(file)

    # Create the Flask application
    app = Flask(__name__)

    # Store schema in app session
    app.config["RULES"] = rules
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
