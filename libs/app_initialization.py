# app_initialization.py

# Standard library imports
import os
from pathlib import Path
from typing import Optional
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer

# Third-party imports
from flask import Flask
from flask_login import LoginManager
from flask_jwt_extended import JWTManager

# Local application/library imports
from libs.redis_wrapper import RedisWrapper
from libs.utils import safe_int, is_base64_encoded
from libs.file_handlers import RuleFileChangeHandler
from libs.connectors.json_user import JsonUserConnector
from libs.auth import expired_token_callback, missing_token_callback
from libs.config_loaders import load_configs, load_schemas, load_rules
from libs.middleware import AllowedIPsMiddleware, DebugLogMiddleware, RequestLoggerMiddleware, callback_logger

# Import logger
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


def _configure_app(app) -> None:
    """
    Configures the Flask app with the necessary settings and environment variables.

    Note: If there is ever a need to invalidate all issued tokens (e.g. a security flaw was found, or the revoked token database was lost),
    this can be easily done by changing the JWT_SECRET_KEY (or Flasks SECRET_KEY, if JWT_SECRET_KEY is unset).

    Args:
        app (Flask): The Flask app instance.

    Raises:
        RuntimeError: If the APP_SECRET_KEY environment variable is not set.

    Returns:
        None
    """
    secret_key = os.environ.get("APP_SECRET_KEY", None)
    jwt_secret_key = os.environ.get("JWT_SECRET_KEY", None)

    # Ensure that the APP_SECRET_KEY environment variable is set
    if secret_key is not None:
        is_base64, secret_key = is_base64_encoded(secret_key)

        if not is_base64:
            secret_key = secret_key.encode("utf-8")
    else:
        logger.error("APP_SECRET_KEY environment variable must be set.")
        raise RuntimeError("APP_SECRET_KEY environment variable must be set.")

    # Ensure that the JWT_SECRET_KEY environment variable is set
    if jwt_secret_key is not None:
        is_base64, jwt_secret_key = is_base64_encoded(jwt_secret_key)

        if not is_base64:
            jwt_secret_key = jwt_secret_key.encode("utf-8")

    else:
        jwt_secret_key = secret_key

    app.secret_key = secret_key

    # TODO: Remove in production
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Max page size for api/requests
    app.config["MAX_PAGE_SIZE"] = safe_int(os.environ.get("MAX_PAGE_SIZE"), 40)

    # Configure JWT settings
    jwt_access_token_expires = safe_int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES"), 600)
    jwt_refresh_token_expires = safe_int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES"), 3600)
    app.config["JWT_SECRET_KEY"] = jwt_secret_key
    app.config["JWT_COOKIE_SECURE"] = True
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True  # CSRF protection
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(seconds=jwt_access_token_expires)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(seconds=jwt_refresh_token_expires)
    app.config["REDIRECT_WHEN_TOKEN_IS_EXPIRED"] = os.environ.get("REDIRECT_WHEN_TOKEN_IS_EXPIRED", False)
    app.config["REDIRECT_WHEN_TOKEN_IS_MISSING"] = os.environ.get("REDIRECT_WHEN_TOKEN_IS_MISSING", False)

    # Set the paths for the rules and configuration files
    app_folder = Path(__file__).parent.parent
    app.config["APP_DIR"] = app_folder
    app.config["CONF_DIR"] = app_folder / "conf"
    app.config["RULES_DIR"] = app_folder / "rules"
    app.config["SCHEMA_DIR"] = app_folder / "schema"

    # Initialize the JWT and LoginManager
    app.config["USER_CONNECTOR"] = JsonUserConnector(app_folder / "users.json")


def _initialize_extensions(app) -> None:
    """
    Initialize extensions for the Flask app.

    Args:
        app: The Flask app instance.

    Returns:
        None
    """
    login_manager = LoginManager(app)
    login_manager.user_loader(app.config["USER_CONNECTOR"].get_user)
    jwt_manager = JWTManager(app)
    jwt_manager.expired_token_loader(expired_token_callback)
    jwt_manager.unauthorized_loader(missing_token_callback)
    jwt_manager.token_in_blocklist_loader(RedisWrapper.is_token_revoked)


def _register_middlewares(app, allowed_ips: Optional[list[str]] = None) -> None:
    """
    Register middlewares for the Flask app.

    Notes:
        - The order in which the middlewares are registered is important. The last middleware is the first to be executed.
        - The RequestLoggerMiddleware is logging the POST requests to /callback/<user_id>.

    Args:
        app (Flask): The Flask app instance.
        allowed_ips (list[str], optional): A list of allowed IP addresses. Defaults to None.

    Returns:
        None
    """
    if allowed_ips is None:
        if not os.environ.get("ALLOWED_IPS", None):
            allowed_ips = []
        else:
            allowed_ips = os.environ.get("ALLOWED_IPS").split(",")

    logger.info(f"Allowed IPs: {allowed_ips}")

    app.wsgi_app = RequestLoggerMiddleware(app=app.wsgi_app, callback=callback_logger, route_regex="^/callback/\\d{1,9}$", methods=["POST"])
    app.wsgi_app = AllowedIPsMiddleware(
        app=app.wsgi_app,
        allowed_ips=allowed_ips,
        trust_proxy=True,
        public_routes=["/health"],
    )

    # Enable debug logging if the LOG_LEVEL environment variable is set to DEBUG
    if os.environ.get("LOG_LEVEL", None) == "DEBUG":
        app.wsgi_app = DebugLogMiddleware(app=app.wsgi_app)


def _start_threads(app: Flask, executor: ThreadPoolExecutor, observer: Observer) -> None:
    """
    Start and manage the threads for loading configurations, schemas, and rules.

    Args:
        app (Flask): The Flask application object.
        executor (ThreadPoolExecutor): The ThreadPoolExecutor instance.
        observer (Observer): The Observer instance.

    Returns:
        None
    """
    event_handler = RuleFileChangeHandler(app=app, executor=executor)
    observer.schedule(event_handler, path=app.config["RULES_DIR"], recursive=False)
    observer.start()

    # Load configurations
    executor.submit(load_configs, app, app.config["CONF_DIR"])

    # Load json schemas and wait until they are loaded
    future_schema = executor.submit(load_schemas, app, app.config["SCHEMA_DIR"])
    future_schema.result()

    # Load rules, ensuring that the schemas were loaded first
    executor.submit(load_rules, app, app.config["RULES_DIR"], app.config["RULES_SCHEMA"])
