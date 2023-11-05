# utils.py

# Standard library imports
import os

# Third-party imports
# ...

# Local application/library imports
from libs.log import setup_logger
from libs.exceptions import PathNotWritableError

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


def write_statement_to_file(
    content: bytes, file_path: str, force: bool = False
) -> None:
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
