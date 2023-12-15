#!/usr/bin/env -S python -W ignore

# test_server.py

# pylint: disable=too-many-locals,redefined-outer-name, unused-argument, unused-argument, unused-import, too-few-public-methods

# Standard library imports
import sys
import pytest
import pytest_mock
from unittest.mock import MagicMock, patch

# Third-party imports
# ...

# Local application/library imports
import server

# Custom exceptions

# Test imports

# Global variables
current_module = sys.modules[__name__]


@pytest.fixture
def mock_external_functions(mocker):
    mocker.patch("server._configure_app")
    mocker.patch("server._initialize_extensions")
    mocker.patch("server._start_threads")
    mocker.spy(server, "_register_all")
    mocker.patch("server._register_middlewares")
    mocker.patch("server.logger")
    mocker.patch("watchdog.observers.Observer")
    mocker.patch("concurrent.futures.ThreadPoolExecutor", return_value=MagicMock())


def test_create_server(mock_external_functions):
    # Create the server
    app = server.create_server()

    # Assert that the app is correctly configured
    assert app is not None

    assert server._register_all.call_count == 1


if __name__ == "__main__":
    pytest.main()
