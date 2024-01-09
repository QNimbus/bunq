# server.py

# Standard library imports
from typing import Callable
from concurrent.futures import ThreadPoolExecutor
from watchdog.observers import Observer

# Third-party imports
from flask import Flask, request

# Local application/library imports
from libs.decorator import routes, error_handlers, before_request_funcs, after_request_funcs, before_request
from libs.app_initialization import _configure_app, _initialize_extensions, _start_threads, _register_middlewares

# Import route handlers
import libs.routes  # pylint: disable=ungrouped-imports,unused-import

from libs import logger  # pylint: disable=ungrouped-imports,unused-import


@before_request
def _register_request_id_handler():
    """
    Registers the request ID to the current request object.

    This function sets the request ID attribute of the request object
    using the value retrieved from the "request_id" key in the request
    environment. If the "request_id" key is not present in the environment,
    the request ID attribute is set to None.

    Parameters:
        None

    Returns:
        None
    """
    setattr(request, "request_id", request.environ.get("request_id", None))


def _register_all(
    app: Flask,
    routes_to_register: list[tuple[str, Callable, dict[str, any]]],
    before_request_funcs_to_register: list[Callable],
    after_request_funcs_to_register: list[Callable],
    error_handlers_to_register: dict[int, Callable],
):
    """
    Register routes, before request functions, after request functions, and error handlers to the Flask application.

    Args:
        app (Flask): The Flask application instance.
        routes_to_register (list[tuple[str, Callable, dict[str, any]]]): A list of tuples containing the route, function, and options.
        before_request_funcs_to_register (list[Callable]): A list of functions to register as before request functions.
        after_request_funcs_to_register (list[Callable]): A list of functions to register as after request functions.
        error_handlers_to_register (dict[int, Callable]): A dictionary containing the error code and the error handler function.
    """
    # Register stored routes
    for rule, f, options in routes_to_register:
        app.route(rule, **options)(f)

    # Register the before request functions
    for f in before_request_funcs_to_register:
        app.before_request(f)

    # Register the after request functions
    for f in after_request_funcs_to_register:
        app.after_request(f)

    # Register error handlers
    for code, f in error_handlers_to_register.items():
        app.errorhandler(code)(f)


def create_server(allowed_ips: list[str] = None) -> Flask:
    """
    Starts the Flask server.

    Returns:
        None
    """
    logger.info(f"Starting server (module: {__name__}))")

    # Create and configure the Flask application
    app = Flask(__name__, static_folder="../frontend/build", static_url_path="/")

    app.observer = Observer()
    app.executor = ThreadPoolExecutor(max_workers=4)

    _configure_app(app)

    _initialize_extensions(app)

    _start_threads(app, app.executor, app.observer)

    _register_all(app, routes, before_request_funcs, after_request_funcs, error_handlers)

    _register_middlewares(app, allowed_ips)

    return app
