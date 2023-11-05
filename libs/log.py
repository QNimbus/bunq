#!/usr/bin/env -S python -W ignore

# logger.py

# Standard library imports
import logging

# Third-party imports
from termcolor import colored

# Local application/library imports
from libs.exceptions import InvalidLogLevelError


class ColoredFormatter(logging.Formatter):
    """
    A formatter that allows coloring of the logs based on the log level.
    """

    COLORS = {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red",
    }

    def format(self, record):
        log_message = super().format(record)
        color = self.COLORS.get(record.levelname, "white")
        return colored(log_message, color)


def setup_logger(name: str, log_level: str = "DEBUG") -> logging.Logger:
    """
    Set up a logger with the specified log level.

    Args:
        name (str): The name of the logger.
        log_level (str): The desired log level, as a string. Valid values are
            'DEBUG', 'INFO', 'WARNING', 'ERROR', and 'CRITICAL'.

    Returns:
        A logging.Logger object.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logging.basicConfig(level=log_level.upper())

        numeric_level = getattr(logging, log_level.upper(), None)

        if not isinstance(numeric_level, int):
            raise InvalidLogLevelError(f"Invalid log level: {log_level}")

        logger.setLevel(numeric_level)
        logger.propagate = False

        handler = logging.StreamHandler()
        handler.setLevel(numeric_level)

        formatter = ColoredFormatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
