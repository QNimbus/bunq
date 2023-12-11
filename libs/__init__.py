# libs/__init__.py

# Standard library imports
import os

# Third-party imports
# ...

# Local application/library imports
from .logger import setup_logger

# Set up logging for the entire libs package
default_log_level = os.environ.get("LOG_LEVEL", "INFO")
logger = setup_logger("libs", default_log_level)
