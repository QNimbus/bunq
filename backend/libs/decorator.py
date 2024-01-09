# decorator.py

# Standard library imports
from typing import Callable

# Third party imports
# ...

# Local application/library imports


routes: list[tuple[str, Callable, dict[str, any]]] = []  # Global variable to store the routes
before_request_funcs: list[Callable] = []  # Global variable to store the before request functions
after_request_funcs: list[Callable] = []  # Global variable to store the after request functions
error_handlers: dict[int, Callable] = {}  # Global variable to store the error handlers


def route(rule: str, **options: dict[str, any]) -> Callable[[Callable], Callable]:
    """
    A decorator function that stores the function and its associated route information.

    Args:
        rule (str): The URL rule as string.
        **options: Variable keyword arguments that can be used to specify additional route options.

    Returns:
        The decorated function.
    """

    def decorator(f: Callable) -> Callable:
        routes.append((rule, f, options))
        return f

    return decorator


def before_request(f: Callable) -> Callable:
    """
    A decorator function that stores the function as a before request function.

    Args:
        f: The function to be stored.

    Returns:
        The decorated function.
    """
    before_request_funcs.append(f)
    return f


def after_request(f: Callable) -> Callable:
    """
    A decorator function that stores the function as an after request function.

    Args:
        f: The function to be stored.

    Returns:
        The decorated function.
    """
    after_request_funcs.append(f)
    return f


def error_handler(code: int) -> Callable[[Callable], Callable]:
    """
    A decorator function that stores the function as an error handler.

    Args:
        code: The error code to be handled.

    Returns:
        The decorated function.
    """

    def decorator(f: Callable):
        error_handlers[code] = f
        return f

    return decorator
