#!/usr/bin/env -S python -W ignore

# test_redis_memoize.py

# pylint: disable=too-many-locals,redefined-outer-name, unused-argument, unused-argument, unused-import, too-few-public-methods

# Standard library imports
from unittest.mock import Mock, patch
import sys
import pickle
import pytest
import pytest_mock

# Third-party imports
# ...

# Local application/library imports
from libs.redis_wrapper import RedisWrapper
from libs.redis_memoizer import RedisMemoizer, JsonSerializer, redis_memoize

# Custom exceptions
from libs.exceptions import RedisMemoizeError, RedisMemoizeRuntimeError

# Test imports
from tests.matchers import String
from tests.helpers import x_squared_function
from tests.helpers import InstanceMethodsClass
from tests.mocks.mock_redis_wrapper import MockRedisWrapper, MockJsonSerializer
from tests.mocks.mock_redis_wrapper import mock_redis_wrapper, mock_json_serializer
from tests.mocks.mock_redis_wrapper import REDIS_WRAPPER, JSON_SERIALIZER, PICKLE

# Global variables
current_module = sys.modules[__name__]


def test_cache_expiry_interaction(mock_redis_wrapper: MockRedisWrapper, mock_json_serializer: MockJsonSerializer, mocker: pytest_mock.MockerFixture):
    """
    Test case for cache expiry using redis_memoize decorator.

    Args:
        mock_redis_wrapper (MockRedisWrapper): Mock Redis wrapper object.
        mock_json_serializer (MockJsonSerializer): Mock JSON serializer object.
        mocker (pytest_mock.MockerFixture): Pytest mocker fixture.
    """

    # Decorated functions
    @redis_memoize(expires=1, secure=False, serializer=mock_json_serializer)
    def memoized_function_short_expiry(x):
        return x * x

    @redis_memoize(expires=2, secure=True, serializer=mock_json_serializer)
    def memoized_function_short_expiry_secure(x):
        return x * x

    mocker.patch(REDIS_WRAPPER, mock_redis_wrapper)

    # Patch the setex method of the mock_redis_wrapper instance
    mocker.spy(mock_redis_wrapper, "setex_secure")
    mocker.spy(mock_redis_wrapper, "setex")

    # Call the function to cache the result
    assert memoized_function_short_expiry(4) == 16
    assert memoized_function_short_expiry_secure(8) == 64

    # Assert that setex was called with the correct expiry time
    mock_redis_wrapper.setex.assert_called_once_with(String(), str(16), 1)

    # Assert that setex was called with the correct expiry time
    mock_redis_wrapper.setex_secure.assert_called_once_with(String(), str(64), 2)


def test_basic_caching(mock_redis_wrapper: MockRedisWrapper, mock_json_serializer: MockJsonSerializer, mocker: pytest_mock.MockerFixture):
    """
    Test case for basic caching using redis_memoize decorator.

    This test case verifies that the decorated function is cached correctly.
    It checks that the function results are equal when called multiple times with the same arguments.
    It also asserts that the result was cached and the function was only executed once.

    Args:
        mock_redis_wrapper: Mock RedisWrapper object.
        mock_json_serializer: Mock JsonSerializer object.
        mocker: Pytest mocker fixture.
    """

    # Create a spy for the regular function in the current module and decorate it
    mocker.spy(current_module, "x_squared_function")
    memoized_x_squared_function = redis_memoize(expires=60, secure=False, serializer=mock_json_serializer)(x_squared_function)

    mocker.patch(REDIS_WRAPPER, mock_redis_wrapper)
    mocker.patch(JSON_SERIALIZER, mock_json_serializer)

    # Spy on the original, undecorated function
    mocker.spy(mock_redis_wrapper, "get")
    mocker.spy(mock_redis_wrapper, "setex")

    # Call the memoized function
    assert memoized_x_squared_function(2) == 4
    mock_redis_wrapper.setex.assert_called_with(key=String(), value=str(4), expires=60)

    assert memoized_x_squared_function(2) == 4  # Should retrieve from cache
    assert memoized_x_squared_function(2) == 4  # Should retrieve from cache

    assert memoized_x_squared_function(8) == 64
    mock_redis_wrapper.setex.assert_called_with(key=String(), value=str(64), expires=60)

    assert memoized_x_squared_function(8) == 64  # Should retrieve from cache
    assert memoized_x_squared_function(8) == 64  # Should retrieve from cache

    # Assert that the 'get' method was called 6 times, to attempt to retrieve from cache
    assert mock_redis_wrapper.get.call_count == 6

    # Assert that the 'setex' method was called twice.
    # To set the cache with an expiry and the results of the memoized function
    assert mock_redis_wrapper.setex.call_count == 2

    # Assert that the memoized function was only called twice.
    # Once for each unique argument, each subsequent call should retrieve from cache
    assert current_module.x_squared_function.call_count == 2


def test_key_generation(mock_redis_wrapper: MockRedisWrapper, mock_json_serializer: MockJsonSerializer, mocker: pytest_mock.MockerFixture):
    """
    Tests the key generation logic in the redis_memoize decorator.

    This test verifies that the redis_memoize decorator generates the correct cache keys for memoized functions.
    It tests key generation for both standalone functions and instance methods. The test ensures that the
    generated keys are in the expected format, incorporating elements like function names, instance identifiers,
    and serialized arguments. It uses mock objects for Redis wrapper and JSON serializer to isolate the test
    from external dependencies. Additionally, the test confirms that the underlying functions are called with
    the correct arguments and the expected number of times.

    Args:
        mock_redis_wrapper (MockRedisWrapper): Mock Redis wrapper object used to simulate Redis interactions.
        mock_json_serializer (MockJsonSerializer): Mock JSON serializer object used to test serialization in key generation.
        mocker (pytest_mock.MockerFixture): Pytest mocker fixture to create spies and mock objects for testing.
    """
    # Create an instance of the class
    instance = InstanceMethodsClass(42)

    # Create a spy for the regular function in the current module and decorate it
    spy_x_squared_function = mocker.spy(current_module, "x_squared_function")
    spy_get_instance_id = mocker.spy(InstanceMethodsClass, "get_instance_id")
    memoized_x_squared_function = redis_memoize(expires=60, secure=False, serializer=mock_json_serializer)(x_squared_function)
    memoized_get_instance_id_1 = redis_memoize(expires=60, secure=False, serializer=mock_json_serializer)(InstanceMethodsClass.get_instance_id)
    memoized_get_instance_id_2 = redis_memoize(expires=60, secure=False, serializer=mock_json_serializer, instance_identifier="instance_id")(InstanceMethodsClass.get_instance_id)
    memoized_get_instance_id_3 = redis_memoize(expires=60, secure=False, serializer=mock_json_serializer, instance_identifier="get_instance_id")(InstanceMethodsClass.get_instance_id)

    mocker.patch(JSON_SERIALIZER, mock_json_serializer)

    with patch(REDIS_WRAPPER, mock_redis_wrapper), patch("libs.redis_memoizer.pickle.dumps") as mock_pickle_dumps, patch("libs.redis_memoizer.id") as mock_id:
        mock_id.return_value = 140386794674448
        mock_pickle_dumps.return_value = b"mocked_pickled_data"

        # Expected key format
        memoized_x_squared_function_expected_key_format = f"standalone:x_squared_function:{mock_pickle_dumps.return_value}"
        memoized_get_instance_id_1_expected_key_format = f"InstanceMethodsClass:140386794674448:get_instance_id:{mock_pickle_dumps.return_value}"
        memoized_get_instance_id_2_expected_key_format = f"InstanceMethodsClass:42:get_instance_id:{mock_pickle_dumps.return_value}"
        memoized_get_instance_id_3_expected_key_format = f"InstanceMethodsClass:42:get_instance_id:{mock_pickle_dumps.return_value}"

        _ = memoized_x_squared_function(3)
        spy_x_squared_function.assert_called_once_with(3)
        mock_pickle_dumps.assert_called_with(((3,), {}))

        # It is necessary to mock the return value of the RedisMemoizer.is_method method because of the way 'is_method' is implemented
        mocker.patch("libs.redis_memoizer.RedisMemoizer.is_method", return_value=True)

        _ = memoized_get_instance_id_1(instance)
        mock_pickle_dumps.assert_called_with(((), {}))

        _ = memoized_get_instance_id_2(instance)
        mock_pickle_dumps.assert_called_with(((), {}))

        # This call should result in the same key as the previous one (instance.get_instance_id() returns instance.instance_id)
        _ = memoized_get_instance_id_3(instance)
        mock_pickle_dumps.assert_called_with(((), {}))

        # Extract the generated key
        generated_keys = list(mock_redis_wrapper.storage.keys())

        # Verify if pickle.dumps was called with the correct arguments (args, kwargs)
        assert mock_pickle_dumps.call_count == 4, "pickle.dumps was not called 4 times"
        assert spy_get_instance_id.call_count == 3, "InstanceMethodsClass.get_instance_id method was not called 3 times"

        # Verify if the generated key matches the expected format
        assert memoized_x_squared_function_expected_key_format == generated_keys[0], "Generated key does not match expected format"
        assert memoized_get_instance_id_1_expected_key_format == generated_keys[1], "Generated key does not match expected format"
        assert memoized_get_instance_id_2_expected_key_format == generated_keys[2], "Generated key does not match expected format"
        assert memoized_get_instance_id_3_expected_key_format == generated_keys[2], "Generated key does not match expected format"


def test_is_method():
    """
    Test the RedisMemoizer.is_method method of the RedisMemoizer class.

    Args:
        mock_redis_wrapper (MockRedisWrapper): Mock Redis wrapper object.
        mock_json_serializer (MockJsonSerializer): Mock JSON serializer object.

    Note: RedisMemoizer.is_standalone_function returns the negation of RedisMemoizer.is_method
    """

    # Test with a regular, standalone function, RedisMemoizer.is_method should return False
    assert RedisMemoizer.is_method(redis_memoize) is False

    # Test with a class instance method, RedisMemoizer.is_method should return True
    assert RedisMemoizer.is_method(RedisMemoizer.__init__) is True
    assert RedisMemoizer.is_method(RedisMemoizer.decorator) is True
    assert RedisMemoizer.is_method(RedisMemoizer(expires=1, secure=False).__init__) is True
    assert RedisMemoizer.is_method(RedisMemoizer(expires=1, secure=False).decorator) is True

    # Test with a class method, RedisMemoizer.is_method should return True for staticmethod
    assert RedisMemoizer.is_method(RedisMemoizer.generate_key) is True
    assert RedisMemoizer.is_method(RedisMemoizer(expires=1, secure=False).generate_key) is True
    assert RedisMemoizer.is_method(RedisMemoizer.generate_key) is True
    assert RedisMemoizer.is_method(RedisMemoizer(expires=1, secure=False).generate_key) is True

    # Test with a class method, RedisMemoizer.is_method should return True for classmethod
    assert RedisMemoizer.is_method(JsonSerializer.serialize) is True
    assert RedisMemoizer.is_method(JsonSerializer.deserialize) is True

    # To satisfy code coverage we need to call RedisMemoizer.is_standalone_function, which is the negation of RedisMemoizer.is_method
    assert RedisMemoizer.is_standalone_function(redis_memoize) is True


def test_redis_memoizer_constructor_raises_error_without_hmac_key():
    """
    Test that the RedisMemoizer constructor raises an error when HMAC secret key is not provided.
    """
    with patch.object(RedisWrapper, "REDIS_HMAC_SECRET_KEY", None):
        with pytest.raises(RedisMemoizeError) as exc_info:
            RedisMemoizer(secure=True)

        assert str(exc_info.value) == "HMAC secret key not provided"


def test_deserialize_data_with_serializer():
    """
    Test case for RedisMemoizer.deserialize_data() deserializing data with a mock serializer.

    The function tests the behavior of the RedisMemoizer.deserialize_data method
    when called with a mock serializer. It verifies that the serializer's deserialize
    method is called with the correct arguments and that the result is the same as
    the original cached data.
    """
    # Create a mock serializer with a `deserialize` method
    mock_serializer = Mock()
    mock_serializer.deserialize.return_value = "deserialized_data"

    # The data to be deserialized
    cached_data = "cached_data"

    # Call the static method
    result = RedisMemoizer.deserialize_data(cached_data=cached_data, serializer=mock_serializer)

    # Check that the serializer's deserialize method was called correctly
    mock_serializer.deserialize.assert_called_once_with(cached_data)

    # Assert that the result is what the mock serializer returned
    assert result == "deserialized_data"


def test_deserialize_data_without_serializer():
    """
    Test case for RedisMemoizer.deserialize_data() deserializing data without a serializer being passed.

    The function tests the behavior of the RedisMemoizer.deserialize_data method
    when called without a serializer. It verifies that the result is the same as
    the original cached data.
    """
    # The data to be deserialized
    cached_data = "cached_data"

    # Call the static method without a serializer
    result = RedisMemoizer.deserialize_data(cached_data, None)

    # Assert that the result is the original cached_data
    assert result == cached_data


def test_decorator_raises_error_on_pickling_error():
    """
    Test that the decorator raises an error when there is a pickling error.

    This test case checks if the decorator raises a RedisMemoizeRuntimeError
    when there is a pickling error while trying to memoize a function.
    """

    # Mock function to be decorated
    def memoized_function(*args, **kwargs):
        pass

    # Create an instance of RedisMemoizer
    memoizer = RedisMemoizer()

    # Apply the decorator
    decorated_func = memoizer.decorator(memoized_function)

    # Replace the 'generate_key' method to raise PicklingError
    with patch.object(RedisMemoizer, "generate_key", side_effect=pickle.PicklingError):
        with pytest.raises(RedisMemoizeRuntimeError) as exc_info:
            decorated_func("some_arg")

    # Assert the raised error message
    assert "Error while pickling data: (some_arg)" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main()
