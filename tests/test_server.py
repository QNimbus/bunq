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


# def test_create_server(mock_external_functions):
#     # Create the server
#     app = server.create_server()

#     # Assert that the app is correctly configured
#     assert app is not None

#     assert server._register_all.call_count == 1


def test_register_all(mock_external_functions):
    # Create a mock Flask app
    app = MagicMock()

    # Define the test data
    routes_to_register = [
        ("/route1", MagicMock(), {}),
        ("/route2", MagicMock(), {}),
    ]
    before_request_funcs_to_register = [MagicMock(), MagicMock()]
    after_request_funcs_to_register = [MagicMock(), MagicMock()]
    error_handlers_to_register = {
        404: MagicMock(),
        500: MagicMock(),
    }

    # Call the function to be tested
    server._register_all(
        app,
        routes_to_register,
        before_request_funcs_to_register,
        after_request_funcs_to_register,
        error_handlers_to_register,
    )

    # Check if the mock was called with specific arguments at any point
    assert app.route.call_count == len(routes_to_register)
    for rule, f, options in routes_to_register:
        found = any(call.args == (rule, *options) for call in app.route.call_args_list)
        assert found, f"app.route was never called with {rule} and {options}"

    # Assert that the before request functions are registered correctly
    assert app.before_request.call_count == len(before_request_funcs_to_register)
    for f in before_request_funcs_to_register:
        found = any(call.args == (f,) for call in app.before_request.call_args_list)
        assert found, f"app.before_request_funcs_to_register was never called with {f}"

    # Assert that the after request functions are registered correctly
    assert app.after_request.call_count == len(after_request_funcs_to_register)
    for f in after_request_funcs_to_register:
        found = any(call.args == (f,) for call in app.after_request.call_args_list)
        assert found, f"app.after_request_funcs_to_register was never called with {f}"

    # Assert that the error handlers are registered correctly
    assert app.errorhandler.call_count == len(error_handlers_to_register)
    for code, f in error_handlers_to_register.items():
        found = any(call.args == (code,) for call in app.errorhandler.call_args_list)
        assert found, f"app.error_handlers_to_register was never called with {code} and {f}"


if __name__ == "__main__":
    pytest.main()
