# server.py

# Standard library imports
import os
import json
import base64
from pathlib import Path
from datetime import datetime
from threading import Thread, Lock, Event, Timer
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, jsonify, request, render_template, current_app

# Local application/library imports
from libs.bunq_lib import BunqLib
from libs.rules import load_rules
from libs.payment import process_payment
from libs.decorator import route, routes, before_request_funcs, before_request as before_request_decorator
from libs.redis_wrapper import RedisWrapper
from libs.exceptions import RuleProcessingError, BunqLibError
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware, RequestLoggerMiddleware, RequestLoggerCallbackData
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


@route("/requests", methods=["GET"])
def requests():
    """
    Handles request log requests via HTTP GET.

    Parameters:
    - None

    Returns:
    - HTML response with a list of request ids.
    """
    request_log = RedisWrapper.get("request_log") or []

    # Get the request data from the Redis database using the request ids in 'request_log'
    logged_requests = {request_id: RedisWrapper.get_secure(request_id) for request_id in request_log}

    # Iterate over the requests
    for request_data in logged_requests.values():
        # Iterate over the request properties
        for key, value in request_data.items():
            # Encode the value to base64 if it is a dict so it's not displayed as a string in the HTML
            # Encode datetime objects to a string
            # Pass the rest of the values as-is
            try:
                if isinstance(value, dict):
                    request_data[key] = base64.b64encode(json.dumps(value).encode("utf-8")).decode("utf-8")
                elif isinstance(value, datetime):
                    request_data[key] = value.strftime("%d-%m-%Y %H:%M:%S")
            except TypeError:
                pass

    return render_template("requests.html", requests=logged_requests)


@route("/replay/<request_uuid>", methods=["GET"])
def replay(request_uuid: str):
    """
    Handles replay requests via HTTP GET.

    Parameters:
    - request_uuid (str): The request id.

    Returns:
    - JSON response with a success message.
    """
    request_data = RedisWrapper.get_secure(request_uuid)

    user_id = int(request_data["url"].split("/")[-1])

    # callback(user_id)

    # # Log the json data
    # callback_logger.info(json.dumps(request_data))

    # callback_data = TypeAdapter(CallbackModel).validate_python(request_data)
    # event_type = callback_data.NotificationUrl.event_type

    # # Dictionary to simulate a switch/case structure
    # switcher = {
    #     "PAYMENT_CREATED": process_payment,
    #     "PAYMENT_RECEIVED": process_payment,
    #     "MUTATION_CREATED": process_payment,
    #     "MUTATION_RECEIVED": process_payment,
    #     "CARD_PAYMENT_ALLOWED": None,
    #     "CARD_TRANSACTION_NOT_ALLOWED": None,
    #     "REQUEST_INQUIRY_CREATED": None,
    #     "REQUEST_INQUIRY_ACCEPTED": None,
    #     "REQUEST_INQUIRY_REJECTED": None,
    #     "REQUEST_RESPONSE_CREATED": None,
    #     "REQUEST_RESPONSE_ACCEPTED": None,
    #     "REQUEST_RESPONSE_REJECTED": None,
    # }

    # # Get the function from switcher dictionary
    # handler = switcher.get(event_type.value, None)

    # # Execute the handler function if it exists and pass the data object
    # if handler is not None and callback_data is not None:
    #     callback_threads.append(Thread(target=handler, kwargs={"app_context": current_app.app_context(), "user_id": 0, "event_type": event_type, "callback_data": callback_data}))
    #     callback_threads[-1].start()
    # else:
    #     logger.info(f"[/replay/{request_uuid}] Unregistered event type {event_type.value}")

    return jsonify({"message": "Success"})


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
            callback_threads.append(
                Thread(
                    target=handler, kwargs={"app_context": current_app.app_context(), "user_id": user_id, "request_id": request.request_id, "event_type": event_type, "callback_data": callback_data}
                )
            )
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


@before_request_decorator
def before_request():
    """
    A function that is executed before each request.

    Returns:
        None
    """
    # Set the request id in the Flask Request object
    setattr(request, "request_id", request.environ.get("request_id", None))


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


def request_logger(environ: dict, request_data: RequestLoggerCallbackData):
    """
    Callback function for the RequestLoggerMiddleware.

    Args:
        request_data (RequestLoggerCallbackData): The request dict.

    Returns:
        None
    """

    def _register_request_thread(request_id: str) -> None:
        """
        Register a request in the Redis database.

        Args:
            app (Flask): The Flask application object.
            lock (Lock): A lock object used for thread synchronization.
            request_id (str): The request id.

        Returns:
            None
        """
        with RedisWrapper.get_lock():
            request_log = RedisWrapper.get("request_log") or []
            request_log.append(request_id)
            RedisWrapper.set("request_log", request_log)

    # Add property 'timestamp' to the request data
    request_data["timestamp"] = datetime.utcnow()

    # Generate a unique id for the request and store in Flask Request object
    request_id = RedisWrapper.generate_uuid()
    environ["request_id"] = request_id

    RedisWrapper.set_secure(request_id, request_data)

    # Register the request in a separate thread
    server_threads.append(Thread(target=_register_request_thread, kwargs={"request_id": request_id}))
    server_threads[-1].start()


def create_server(allowed_ips: list[str] = None) -> Flask:
    """
    Starts the Flask server.

    Returns:
        None
    """
    logger.info("Starting server")

    # Create the Flask application
    app = Flask(__name__, template_folder="html")
    lock_app_config = Lock()

    if allowed_ips is None:
        if os.environ.get("ALLOWED_IPS", None) is None:
            allowed_ips = []
        else:
            allowed_ips = os.environ.get("ALLOWED_IPS").split(",")

    logger.info(f"Allowed IPs: {allowed_ips}")

    # TODO: Remove in production
    app.config["TEMPLATES_AUTO_RELOAD"] = True

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

    # Register the before request functions
    for f in before_request_funcs:
        app.before_request(f)

    # Register middlewares
    app.wsgi_app = AllowedIPsMiddleware(
        app=app.wsgi_app,
        allowed_ips=allowed_ips,
        trust_proxy=True,
        public_routes=["/health"],
    )

    app.wsgi_app = RequestLoggerMiddleware(app=app.wsgi_app, route_regex="^/callback/\\d{1,9}$", callback=request_logger)

    # If environment variable 'LOG_LEVEL' is set to 'DEBUG', enable the DebugLogMiddleware
    if os.environ.get("LOG_LEVEL", None) == "DEBUG":
        app.wsgi_app = DebugLogMiddleware(app=app.wsgi_app)

    return app
