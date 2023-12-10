# decorator.py

# Standard library imports
import os

# Local application/library imports
from libs.logger import setup_logger

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


routes = []  # Global variable to store the routes
before_request_funcs = []  # Global variable to store the before request functions


def route(rule: str, **options):
    """
    A decorator function that stores the function and its associated route information.

    Args:
        rule (str): The URL rule as string.
        **options: Variable keyword arguments that can be used to specify additional route options.

    Returns:
        The decorated function.
    """

    def decorator(f):
        # Store the function and its associated route information
        routes.append((rule, f, options))
        return f

    return decorator


def before_request(f):
    # Store the function as a before request function
    before_request_funcs.append(f)
    return f
