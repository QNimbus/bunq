# file_handlers.py

# Standard library imports
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent

# Third-party imports
from flask import Flask

# Local application/library imports
from libs.config_loaders import load_rules

# Import logger
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


class RuleFileChangeHandler(FileSystemEventHandler):
    """
    A class that handles file change events for rule files.

    Attributes:
        app (Flask): The Flask application object.
        executor (ThreadPoolExecutor): The ThreadPoolExecutor instance.

    Methods:
        on_modified: Event handler for file modification events.
    """

    def __init__(self, app: Flask, executor: ThreadPoolExecutor):
        """
        Initialize the RuleFileChangeHandler.

        Args:
            app (Flask): The Flask application object.
            executor (ThreadPoolExecutor): The ThreadPoolExecutor instance.

        """
        self.app = app
        self.executor = executor
        self._future = None

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        """
        Event handler for file modification events.

        Args:
            event (DirModifiedEvent | FileModifiedEvent): The event that was triggered.

        Returns:
            None
        """
        if event.is_directory:
            return

        if event.src_path.endswith(".rules.json"):
            # Wait for any previous load_rules_thread to finish
            if self._future is None or self._future.done():
                logger.info(f"Detected change in {event.src_path}. Reloading rules...")
                self._future = self.executor.submit(load_rules, app=self.app, rules=Path(event.src_path), rules_schema=self.app.config["RULES_SCHEMA"])
