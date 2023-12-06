# server.py

# Standard library imports
import os
import json
from pathlib import Path
from threading import Thread, Lock, Event, Timer
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, jsonify, request, current_app

# Local application/library imports
from libs.bunq_lib import BunqLib
from libs.rules import load_rules
from libs.payment import process_payment
from libs.decorator import route, routes
from libs.exceptions import RuleProcessingError, BunqLibError
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware
from libs.logger import setup_logger, setup_logger_with_rotating_file_handler
from schema.rules_model import RuleModel
from schema.callback_model import CallbackModel


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

server_threads = []
callback_threads = []


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
        return jsonify({"message": "Unkown user"}), 400

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
            callback_threads.append(Thread(target=handler, kwargs={"app_context": current_app.app_context(), "user_id": user_id, "event_type": event_type, "callback_data": callback_data}))
            callback_threads[-1].start()
        else:
            logger.info(f"[/callback/{user_id}] Unregistered event type {event_type.value}")

        return jsonify({"message": "Success"})
    except ValidationError:
        # Log the failed callback json data
        failed_callback_logger.info(json.dumps(request_data))

        logger.info(f"[/callback/{user_id}] Schema mismatch: {request}")

        # Return HTTP 400 if the callback data did not match the schema
        return jsonify({"message": "Schema mismatch"}), 400


class RuleFileChangeHandler(FileSystemEventHandler):
    """
    A class that handles file change events for rule files.

    Attributes:
        app (Flask): The Flask application object.
        lock (Lock): A lock object for thread synchronization.

    Methods:
        load_rules_thread(app: Flask) -> None:
            Load rules from JSON files in the specified directory and store them in the app's configuration.

        on_modified(event) -> None:
            Event handler for file modification events.
    """

    def __init__(self, app: Flask, event: Event, lock: Lock = None):
        """
        Initialize the RuleFileChangeHandler.

        Args:
            app (Flask): The Flask application object.
            event (Event): The event object used to signal when the schemas are loaded.
            lock (Lock, optional): A lock object for thread synchronization. Defaults to None.
        """
        self.app = app
        self.event = event
        self.debounce_timer = None

        if lock is None:
            self.lock = Lock()
        else:
            self.lock = lock

    def on_modified(self, event) -> None:
        """
        Event handler for file modification events.

        Args:
            _event: The file modification event.

        Returns:
            None
        """
        # Start a new load_rules_thread when a file is modified
        if event.is_directory:
            return

        if self.debounce_timer is not None:
            self.debounce_timer.cancel()

        self.debounce_timer = Timer(0.1, lambda: (load_rules_thread(app=self.app, lock=self.lock, schemas_loaded=self.event), logger.info("Rules changed, reloading rules"))[0])
        self.debounce_timer.start()


def load_rules_thread(app: Flask, lock: Lock, schemas_loaded: Event) -> None:
    """
    Load rules from JSON files in a separate thread and update the app configuration.

    Args:
        app (Flask): The Flask application object.
        lock (Lock): A lock object used for thread synchronization.
        schemas_loaded (Event): An event object used to signal when the schemas are loaded.

    Returns:
        None
    """
    try:
        # Wait for the schemas to be loaded
        schemas_loaded.wait()

        rules: RuleModel = {}
        rules_dir: Path = app.config["RULES_DIR"]
        rules_schema: dict = app.config["RULES_SCHEMA"]
        for file in rules_dir.glob("*.rules.json"):
            rules_file = rules_dir / file
            rules[file.name] = load_rules(schema=rules_schema, rules_path=rules_file)
            logger.info(f"Loaded rules from {rules_file}")

        # Use the lock to ensure thread-safe writing to app.config
        with lock:
            app.config["RULES"] = rules

        # Signal that the schemas are loaded
        schemas_loaded.set()
    except RuleProcessingError as error:
        logger.error(error)


def load_config_thread(app: Flask, lock: Lock, configurations_loaded: Event) -> None:
    """
    Load configuration from JSON files in a separate thread and update the app configuration.

    Args:
        app (Flask): The Flask application object.
        lock (Lock): A lock object used for thread synchronization.

    Returns:
        None
    """
    try:
        bunq_configs: dict[str, BunqLib] = {}
        conf_dir: Path = app.config["CONF_DIR"]
        for file in conf_dir.glob("*.conf"):
            # Use the lock to ensure thread-safe loading of BunqLib instances
            with lock:
                conf_file = conf_dir / file
                bunq_lib = BunqLib(production_mode=True, config_file=conf_file)
                bunq_configs[bunq_lib.user_id] = bunq_lib
                logger.info(f"Initialized BunqLib for user '{bunq_lib.user.display_name}' with config file: {conf_file}")

        # Use the lock to ensure thread-safe writing to app.config
        with lock:
            app.config["BUNQ_CONFIGS"] = bunq_configs
            configurations_loaded.set()

    except BunqLibError as error:
        logger.error(error)


def load_schema_thread(app: Flask, lock: Lock, schema_loaded: Event, schema_name: str) -> None:
    """
    Load the rules schema from the schema file in a separate thread and update the app configuration.

    Args:
        app (Flask): The Flask application object.
        lock (Lock): A lock object used for thread synchronization.
        schema_loaded (Event): An event object used to signal that the schema has been loaded.

    Returns:
        None
    """
    try:
        rules_schema: dict = {}
        schema_dir: Path = app.config["SCHEMA_DIR"]
        schema_file = schema_dir / f"{schema_name}.schema.json"
        with open(schema_file, "r", encoding="utf-8") as file:
            rules_schema = json.load(file)
            logger.info(f"Loaded rules schema from {schema_file}")

        # Use the lock to ensure thread-safe writing to app.config
        with lock:
            key = schema_name.upper() + "_SCHEMA"
            app.config[key] = rules_schema
            schema_loaded.set()

    except (FileNotFoundError, PermissionError) as error:
        logger.error(error)
    except json.JSONDecodeError as error:
        logger.error(error)


def create_server(allowed_ips: list[str] = None) -> Flask:
    """
    Starts the Flask server.

    Returns:
        None
    """
    logger.info("Starting server")

    # Create the Flask application
    app = Flask(__name__)
    lock_app_config = Lock()

    if allowed_ips is None:
        if os.environ.get("ALLOWED_IPS", None) is None:
            allowed_ips = []
        else:
            allowed_ips = os.environ.get("ALLOWED_IPS").split(",")

    logger.info(f"Allowed IPs: {allowed_ips}")

    # Set the paths for the rules and configuration files
    app.config["CONF_DIR"] = Path(__file__).parent / "conf"
    app.config["RULES_DIR"] = Path(__file__).parent / "rules"
    app.config["SCHEMA_DIR"] = Path(__file__).parent / "schema"

    # Register a file change handler to reload the rules when a file is modified
    observer = Observer()
    rule_schemas_loaded = Event()
    callback_schemas_loaded = Event()
    configurations_loaded = Event()
    rule_file_change_handler = RuleFileChangeHandler(app=app, event=rule_schemas_loaded, lock=lock_app_config)
    observer.schedule(rule_file_change_handler, path=app.config["RULES_DIR"])
    observer.start()

    # Load schemas in a separate thread
    server_threads.append(Thread(target=load_schema_thread, args=(app, lock_app_config, rule_schemas_loaded, "rules")))
    server_threads.append(Thread(target=load_schema_thread, args=(app, lock_app_config, callback_schemas_loaded, "callback")))

    # Load rules in a separate thread
    server_threads.append(Thread(target=load_rules_thread, args=(app, lock_app_config, rule_schemas_loaded)))

    # Initialize BunqApp instances
    server_threads.append(Thread(target=load_config_thread, args=(app, lock_app_config, configurations_loaded)))

    # Start all threads
    for thread in server_threads:
        thread.start()

    # Wait for all threads to complete
    for thread in server_threads:
        thread.join()

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
