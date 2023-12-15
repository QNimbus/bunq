# utils.py

# Standard library imports
import os
import base64
from urllib.parse import urlparse, urljoin

# Third-party imports
from flask import Request, url_for, current_app, request as flask_request

# Local application/library imports
from libs.exceptions import PathNotWritableError

# Import logging
from . import logger


def write_statement_to_file(content: bytes, file_path: str, force: bool = False) -> None:
    """
    Write the statement content to a local file.

    Parameters:
    - content (bytes): The statement content in bytes.
    - file_path (str): The path of the file where the content will be written. If a filename is provided without a path,
                       the file will be written to the current working directory.
    - force (bool): A flag that if set to True, overwrites the file if it already exists.

    Raises:
    - FileExistsError: If the file already exists and force is False.
    - FileNotFoundError: If the provided directory path does not exist.
    - PathNotWritableError: If the file path is not writable.
    - IOError: If there is an error in writing to the file.

    Example:
    >>> statement = Statement()
    >>> content = statement.export_statement(1, 12345)
    >>> write_statement_to_file(content, 'file.txt', force=True)
    """

    dir_name = os.path.dirname(file_path) or "."

    if not os.path.exists(dir_name):
        raise FileNotFoundError(f"The directory does not exist: {dir_name}")

    if not os.access(dir_name, os.W_OK):
        raise PathNotWritableError(f"The path is not writable: {dir_name}")

    if os.path.exists(file_path) and not force:
        raise FileExistsError(f"The file already exists: {file_path}")

    try:
        with open(file_path, "wb") as file:
            file.write(content)

    except Exception as exc:
        raise IOError(f"Error writing content to file: {exc}") from exc


def safe_int(i: str, default: int = 0) -> int:
    """
    Safely converts a string to an integer.

    Parameters:
    - i (str): The string to be converted to an integer.
    - default (int): The default value to return if the conversion fails.

    Returns:
    - int: The converted integer value or the default value if the conversion fails.
    """
    try:
        return int(i)
    except (TypeError, ValueError):
        return default


def is_safe_url(*, request: Request, target: str, require_https: bool = True) -> bool:
    """
    Check if a target URL is safe to redirect to.

    This function is used to prevent unvalidated redirects and forwards, which is a type of web application vulnerability.
    It does this by ensuring that the target URL uses the same scheme (HTTP or HTTPS) and netloc (network location, or domain) as the request's host URL.

    Parameters:
    - request (Request): The Flask request object.
    - target (str): The target URL to check.
    - require_https (bool): A flag indicating whether the target URL must use HTTPS. Default is True.

    Returns:
    - bool: True if the target URL is safe to redirect to, False otherwise.
    """
    try:
        ref_url = urlparse(request.host_url)
        test_url = urlparse(urljoin(request.host_url, target))
    except ValueError as e:
        logger.warning(f"Failed to parse URLs in is_safe_url: {e}")
        return False

    valid_protocols = ("http", "https") if require_https else ("http",)

    is_safe = test_url.scheme in valid_protocols and ref_url.netloc == test_url.netloc

    if not is_safe:
        logger.warning(f"Unsafe redirect detected: request host URL is {request.host_url}, target URL is {target}")

    return is_safe


def is_valid_next_url(next_url: str) -> bool:
    """
    Check if the next_url corresponds to a valid endpoint in the application.

    Args:
        next_url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    if not is_local_domain(next_url):
        return False

    # Extract the path from next_url if it's a full URL
    path = urlparse(next_url).path

    # Convert path to an endpoint and arguments
    try:
        endpoint, _ = current_app.url_map.bind("").match(path, method="GET")
    except Exception:  # pylint: disable=broad-except
        return False

    # Optional: Check if endpoint corresponds to a function
    if not endpoint in current_app.view_functions:
        return False

    return True


def is_local_domain(url: str) -> bool:
    """
    Check if the domain of the given URL matches the Flask app's domain.

    Args:
        url (str): The URL to check.

    Returns:
        bool: True if domains match, False otherwise.
    """
    parsed_url = urlparse(url)
    app_domain = urlparse(flask_request.host_url).netloc

    # If the URL has no domain (i.e., it's a relative path), consider it matching
    return parsed_url.netloc == app_domain if parsed_url.netloc else True


def are_urls_equal(url_1: str, url_2: str, compare_query: bool = False) -> bool:
    """
    Check if two URLs are equal.

    Args:
        url_1 (str): The first URL.
        url_2 (str): The second URL.
        compare_query (bool): Whether to include the query string in the comparison.

    Returns:
        bool: True if the URLs are equal, False otherwise.
    """

    def _get_absolute_url(url):
        parsed_url = urlparse(url)
        if parsed_url.scheme:
            return url  # Already an absolute URL
        try:
            # Attempt to resolve as an endpoint
            return url_for(url, _external=True)
        except Exception:  # pylint: disable=broad-except
            # Assume it's a path and make it absolute
            return urljoin(flask_request.host_url, url)

    absolute_url1 = _get_absolute_url(url_1)
    absolute_url2 = _get_absolute_url(url_2)

    parsed_url1 = urlparse(absolute_url1)
    parsed_url2 = urlparse(absolute_url2)

    if compare_query:
        return (parsed_url1.scheme, parsed_url1.netloc, parsed_url1.path, parsed_url1.query) == (parsed_url2.scheme, parsed_url2.netloc, parsed_url2.path, parsed_url2.query)

    return (parsed_url1.scheme, parsed_url1.netloc, parsed_url1.path) == (parsed_url2.scheme, parsed_url2.netloc, parsed_url2.path)


def is_base64_encoded(s: str) -> tuple[bool, str]:
    """
    Check if a string is base64 encoded.

    Args:
        s (str): The string to be checked.

    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the string is base64 encoded and the decoded string.
    """
    try:
        decoded = base64.b64decode(s)
        return True, decoded
    except Exception:  # pylint: disable=broad-except
        return False, s
