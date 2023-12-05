#!/usr/bin/env -S python -W ignore

# logger.py

# Standard library imports
import os
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
        pid = os.getpid()
        log_message = f"[PID: {pid}] {log_message}"
        return colored(log_message, color)


def setup_logger(name: str, log_level: str = "DEBUG", use_color: bool = False) -> logging.Logger:
    """
    Set up a logger with the specified log level.

    Args:
        name (str): The name of the logger.
        log_level (str): The desired log level, as a string. Valid values are 'DEBUG', 'INFO', 'WARNING', 'ERROR', and 'CRITICAL'.
        use_color (bool): Whether to use colors in the log messages.

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

        pid = os.getpid()

        if use_color:
            formatter = ColoredFormatter(
                fmt=f"[%(asctime)s] [{pid}] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S %z",
            )
        else:
            formatter = logging.Formatter(
                fmt=f"[%(asctime)s] [{pid}] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S %z",
            )

        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger


def setup_logger_with_rotating_file_handler(
    name: str,
    filename: str,
    log_level: str = "DEBUG",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Set up a logger with a rotating file handler.

    Args:
        name (str): The name of the logger.
        filename (str, optional): The name of the log file. Defaults to "logs/app.log".
        log_level (str, optional): The log level. Defaults to "DEBUG".
        max_bytes (int, optional): The maximum size of the log file in bytes. Defaults to 10 * 1024 * 1024.
        backup_count (int, optional): The number of backup log files to keep. Defaults to 5.

    Returns:
        logging.Logger: The logger object.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logging.basicConfig(level=log_level.upper())

        numeric_level = getattr(logging, log_level.upper(), None)

        if not isinstance(numeric_level, int):
            raise InvalidLogLevelError(f"Invalid log level: {log_level}")

        logger.setLevel(numeric_level)
        logger.propagate = False

        # Get current process id
        pid = os.getpid()

        # If filename has extension, use it as is. Otherwise, append .<pid>.log to it.
        if not filename.endswith(".log"):
            filename = f"{filename}.{pid}.log"
        else:
            # Replace the extension with .<pid>.log
            filename = f"{filename.rsplit('.', 1)[0]}.{pid}.log"

        handler = logging.handlers.RotatingFileHandler(filename=filename, maxBytes=max_bytes, backupCount=backup_count)
        handler.setLevel(numeric_level)

        # Setup a formatter wihtout colors:
        formatter = logging.Formatter(fmt="%(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
