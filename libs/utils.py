# utils.py

# Standard library imports
import os

# Third-party imports
from urllib.parse import urlparse, urljoin
from flask import Request

# Local application/library imports
from . import logger
from libs.exceptions import PathNotWritableError


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
    except ValueError:
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
