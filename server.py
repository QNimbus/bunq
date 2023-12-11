# server.py

# Standard library imports
import os
import json
import base64
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from threading import Thread, Lock, Event, Timer
from datetime import datetime, timedelta, timezone
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Third-party imports
from pydantic import TypeAdapter
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from flask import Flask, Response, jsonify, render_template, redirect, url_for, make_response, request, current_app
from flask_login import LoginManager
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
    get_jwt,
    get_jwt_identity,
    verify_jwt_in_request,
    jwt_required,
    create_refresh_token,
    set_refresh_cookies,
)
from flask_jwt_extended.exceptions import NoAuthorizationError

# Local application/library imports
from libs.bunq_lib import BunqLib
from libs.user import User, UserConnector
from libs.rules import load_rules
from libs.payment import process_payment
from libs.utils import safe_int, is_safe_url
from libs.connectors.json_user import JsonUserConnector
from libs.redis_wrapper import RedisWrapper
from libs.exceptions import RuleProcessingError, BunqLibError
from libs.logger import setup_logger
from libs.decorator import (
    route,
    routes,
    error_handlers,
    before_request_funcs,
    after_request_funcs,
    before_request as before_request_decorator,
    after_request as after_request_decorator,
)
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware, RequestLoggerMiddleware, RequestLoggerCallbackData
from schema.rules_model import RuleModel
from schema.callback_model import CallbackModel

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))
# callback_logger = setup_logger_with_rotating_file_handler(
#     "callback",
#     log_level="INFO",
#     filename="logs/callback.log",
#     max_bytes=100 * 1024 * 1024,
#     backup_count=5,
# )
# failed_callback_logger = setup_logger_with_rotating_file_handler(
#     "fail",
#     log_level="INFO",
#     filename="logs/fail.log",
#     max_bytes=100 * 1024 * 1024,
#     backup_count=5,
# )

server_threads = []


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


@route("/api/requests", methods=["GET"])
@jwt_required()
def api_requests():
    """
    Retrieves all request data from Redis and returns it as a JSON response.
    """
    try:
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 10, type=int)

        if page < 1 or page_size < 1:
            raise ValueError("Page and page size must be positive integers.")

        # Set a maximum page_size to avoid very large requests
        max_page_size = current_app.config["MAX_PAGE_SIZE"]
        page_size = min(page_size, max_page_size)

        all_request_data = RedisWrapper.get_all_request_data()

        # Iterate over the request_data
        for _uuid, request_data in all_request_data.items():
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

        # Apply pagination
        data_list = list(all_request_data.items())
        data_list.reverse()
        start = (page - 1) * page_size
        end = start + page_size
        page_data = data_list[start:end]

        total_items = len(all_request_data)
        total_pages = total_items // page_size + (total_items % page_size > 0)

        return jsonify({"data": page_data, "total_items": total_items, "total_pages": total_pages, "current_page": page, "page_size": page_size})
    except ValueError as error:
        logger.error(error)
        return jsonify({"message": "Internal server error"}), 500


@route("/api/requests/<request_id>", methods=["DELETE"])
@jwt_required()
def delete_request(request_id: str):
    """
    Deletes a request from Redis.

    Parameters:
    - request_id (str): The request id.

    Returns:
    - JSON response with a success message.
    """
    RedisWrapper.remove_request_data(request_id=request_id)
    return jsonify({"message": "Success"})


@route("/requests", methods=["GET"])
@jwt_required()
def requests():
    """
    Handles request log requests via HTTP GET.

    Parameters:
    - None

    Returns:
    - HTML response with a list of request ids.
    """
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: User = user_connector.get_user(get_jwt_identity())

    return render_template("requests.html", user=user)


@route("/replay/<request_uuid>", methods=["GET"])
@jwt_required(fresh=True)
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
    request_id = request.environ.get("request_id", None)

    if request_id is None:
        raise RuntimeError(f"Request id not set in request: {request}")

    # Get request_log from Redis. If it does not exist, throw an error
    current_request = RedisWrapper.get_request_data(request_id=request_id)

    if current_request is None:
        raise RuntimeError(f"Request id not found in request_log: {request_id}")

    # Return 400 if the request is not JSON
    if not request.is_json:
        response_message = {"message": "Missing JSON in request"}
        current_request["response"] = response_message

        # Register the response in a separate thread
        Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()

        logger.info(f"[/callback/{user_id}] Invalid request: {request}")
        return jsonify(response_message), 400

    # Fetch all available user ids from the app session
    keys = current_app.config["BUNQ_CONFIGS"].keys() if "BUNQ_CONFIGS" in current_app.config else []

    if user_id not in keys:
        response_message = {"message": "Invalid user"}
        current_request["response"] = response_message

        # Register the response in a separate thread
        Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()

        logger.info(f"[/callback/{user_id}] Invalid user id: {user_id}")
        return jsonify(response_message), 400

    try:
        request_data = request.get_json()
        request_schema = current_app.config["CALLBACK_SCHEMA"]

        # Validate the request data against the schema
        validate(instance=request_data, schema=request_schema)

        # Log the json data
        # callback_logger.info(json.dumps(request_data))

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
            current_request["processed"] = True
            current_request["event"] = event_type.value

            # Register the response in a separate thread
            Thread(target=RedisWrapper.set_request_data, kwargs={"request_id": request_id, "data": current_request}).start()
            Thread(
                target=handler, kwargs={"app_context": current_app.app_context(), "user_id": user_id, "request_id": request.request_id, "event_type": event_type, "callback_data": callback_data}
            ).start()
        else:
            logger.info(f"[/callback/{user_id}] Unregistered event type {event_type.value}")

        return jsonify({"message": "Success"})
    except ValidationError:
        # Log the failed callback json data
        # failed_callback_logger.info(json.dumps(request_data))

        logger.info(f"[/callback/{user_id}] Schema mismatch: {request}")

        # Return HTTP 400 if the callback data did not match the schema
        return jsonify({"message": "Schema mismatch"}), 400


@route("/", methods=["GET"])
def main():
    """
    Returns the main page.

    Returns:
        HTML response with the main page.
    """
    return render_template("main.html", next="/requests")


@route("/login", methods=["POST"])
def login():
    """
    Authenticates the user's credentials and generates an access token if the credentials are valid.

    Returns:
        If the credentials are valid, returns a JSON response containing the access token with a status code of 200.
        If the request is missing JSON or the username/password is missing, returns a JSON response with an error message and a status code of 400.
        If the username/password is incorrect, returns a JSON response with an error message and a status code of 401.
    """
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    username = request.json.get("username", None)
    password = request.json.get("password", None)

    if not username or not password:
        return jsonify({"msg": "Missing username or password"}), 400

    # This should check your user's credentials from the database
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: Optional[User] = user_connector.authenticate(username, password)

    if user:
        # Create tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        # Determine redirect URL
        redirect_url = request.json.get("next") or request.args.get("next") or url_for("main")
        if not is_safe_url(target=redirect_url, request=request, require_https=True):
            redirect_url = url_for("main")

        # Create a redirect response
        response = make_response(redirect(redirect_url))

        # Set the JWT cookies
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)

        return response

    return jsonify({"msg": "Bad username or password"}), 401


@route("/token/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refreshes the JWT token for the current user.

    Returns:
        response (flask.Response): The response object with the refreshed token.
    """
    user_connector: UserConnector = current_app.config["USER_CONNECTOR"]
    user: Optional[User] = user_connector.get_user(get_jwt_identity())

    if not user:
        response = jsonify({"msg": "User not found"})
        unset_jwt_cookies(response)
        return response, 404

    new_token = create_access_token(identity=user.id, fresh=False)

    response = jsonify({"msg": "Token refreshed"})
    set_access_cookies(response, new_token)
    return response, 200


@route("/logout", methods=["GET"])
def logout():
    """
    Logs out the user by unsetting the JWT cookie.

    Returns:
        JSON response with a success message.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", ""):
        response = jsonify({"msg": "Successfully logged out"})
        unset_jwt_cookies(response)
        return response, 200

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True):
        redirect_url = url_for("main")

    response = make_response(redirect(redirect_url))
    unset_jwt_cookies(response)
    return response


def expired_token_callback(expired_token_header: dict, _expired_token_payload: dict):
    """
    Callback function to handle expired tokens.

    Args:
        expired_token_header (dict): The expired token.
        _expired_token_payload (dict): The payload of the expired token.

    Returns:
        flask.Response: The response object with appropriate status code, message, and headers.
    """
    token_type = expired_token_header["typ"]

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "") or any(request.path.startswith(path) for path in ["/api/", "/token/"]):
        response = jsonify({"msg": "Token has expired"})
        response.headers["Token-Expired"] = token_type
        return response, 401

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True):
        redirect_url = url_for("main")

    # Url encode the redirect url
    response = make_response(redirect(redirect_url + "?next=" + quote_plus(request.url)))
    response.headers["Token-Expired"] = token_type
    return response


def missing_token_callback(reason: str):
    """
    Callback function for handling missing token error.

    Args:
        reason (str): The reason for the missing token.

    Returns:
        tuple: A tuple containing the response and status code.
    """
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "") or any(request.path.startswith(path) for path in ["/api/", "/token/"]):
        response = jsonify({"msg": reason})
        return response, 401

    # Determine redirect URL
    redirect_url = request.args.get("next") or url_for("main")
    if not is_safe_url(target=redirect_url, request=request, require_https=True):
        redirect_url = url_for("main")

    # Url encode the redirect url
    response = make_response(redirect(redirect_url + "?next=" + quote_plus(request.url)))
    return response


@before_request_decorator
def before_request():
    """
    A function that is executed before each request.

    Returns:
        None
    """
    setattr(request, "request_id", request.environ.get("request_id", None))


@after_request_decorator
def refresh_expiring_jwts(response: Response) -> Response:
    """
    Refreshes expiring JWTs by checking the expiration timestamp of the current JWT.
    If the JWT is expiring within the next 10 minutes, a new access token is created
    and set as a cookie in the response.

    Args:
        response (Response): The original response object.

    Returns:
        Response: The updated response object.
    """
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"] * 0.3)
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(identity=get_jwt_identity())
            set_access_cookies(response, access_token)
        return response
    except (RuntimeError, KeyError):
        # Case where there is not a valid JWT. Just return the original response
        return response


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


def callback_logger(environ: dict, request_data: RequestLoggerCallbackData):
    """
    Callback function for the RequestLoggerMiddleware.

    Args:
        request_data (RequestLoggerCallbackData): The request dict.

    Returns:
        None
    """
    # Generate a unique id for the request and store in Flask Request object
    request_id = RedisWrapper.generate_uuid()
    request_data["id"] = request_id
    request_data["processed"] = False
    request_data["timestamp"] = datetime.utcnow()

    environ["request_id"] = request_id

    RedisWrapper.set_request_data(request_id=request_id, data=request_data)

    # Register the request in a separate thread
    Thread(target=RedisWrapper.log_request, kwargs={"request_id": request_id}).start()


def create_server(allowed_ips: list[str] = None) -> Flask:
    """
    Starts the Flask server.

    Returns:
        None
    """
    logger.info("Starting server")

    # Create the Flask application
    app = Flask(__name__, template_folder="html")
    secret_key = os.environ.get("APP_SECRET_KEY", None)
    jwt_secret_key = os.environ.get("JWT_SECRET_KEY", None)

    # Ensure that the APP_SECRET_KEY environment variable is set
    if secret_key is None or jwt_secret_key is None:
        logger.error("Both APP_SECRET_KEY and JWT_SECRET_KEY environment variables must be set; currently, one or both are missing.")
        raise RuntimeError("Both APP_SECRET_KEY and JWT_SECRET_KEY environment variables must be set; currently, one or both are missing.")

    app.secret_key = secret_key.encode("utf-8")

    # Max page size for api/requests
    app.config["MAX_PAGE_SIZE"] = safe_int(os.environ.get("MAX_PAGE_SIZE"), 100)

    # TODO: Remove in production
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Set the JWT secret key
    jwt_access_token_expires = safe_int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES"), 600)
    jwt_refresh_token_expires = safe_int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES"), 86400)
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", None)
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=jwt_access_token_expires)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=jwt_refresh_token_expires)
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # CSRF protection
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = True

    # Set the paths for the rules and configuration files
    app.config["CONF_DIR"] = Path(__file__).parent / "conf"
    app.config["RULES_DIR"] = Path(__file__).parent / "rules"
    app.config["SCHEMA_DIR"] = Path(__file__).parent / "schema"

    # Initialize the JWT and LoginManager
    app.config["USER_CONNECTOR"] = JsonUserConnector(Path(__file__).parent / "users.json")
    login_manager = LoginManager(app)
    login_manager.user_loader(app.config["USER_CONNECTOR"].get_user)
    jwt_manager = JWTManager(app)
    jwt_manager.expired_token_loader(expired_token_callback)
    jwt_manager.unauthorized_loader(missing_token_callback)

    lock_app_config = Lock()

    if allowed_ips is None:
        if os.environ.get("ALLOWED_IPS", None) is None:
            allowed_ips = []
        else:
            allowed_ips = os.environ.get("ALLOWED_IPS").split(",")

    logger.info(f"Allowed IPs: {allowed_ips}")

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

    # Remove threads from list
    server_threads.clear()

    # Register stored routes
    for rule, f, options in routes:
        app.route(rule, **options)(f)

    # Register the before request functions
    for f in before_request_funcs:
        app.before_request(f)

    # Register the after request functions
    for f in after_request_funcs:
        app.after_request(f)

    # Register error handlers
    for code, f in error_handlers.items():
        app.errorhandler(code)(f)

    # Register middlewares
    app.wsgi_app = AllowedIPsMiddleware(
        app=app.wsgi_app,
        allowed_ips=allowed_ips,
        trust_proxy=True,
        public_routes=["/health"],
    )

    app.wsgi_app = RequestLoggerMiddleware(app=app.wsgi_app, callback=callback_logger, route_regex="^/callback/\\d{1,9}$", methods=["POST"])

    # If environment variable 'LOG_LEVEL' is set to 'DEBUG', enable the DebugLogMiddleware
    if os.environ.get("LOG_LEVEL", None) == "DEBUG":
        app.wsgi_app = DebugLogMiddleware(app=app.wsgi_app)

    return app
