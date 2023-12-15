# mock_redis_wrapper.py

# Standard library imports
import pytest

# Third-party imports

# Local application/library imports

REDIS_WRAPPER = "libs.redis_memoizer.RedisWrapper"
JSON_SERIALIZER = "libs.redis_memoizer.JsonSerializer"
PICKLE = "libs.redis_memoizer.pickle"


class MockRedisWrapper:
    """
    A mock implementation of a Redis wrapper for testing purposes.
    """

    REDIS_HMAC_SECRET_KEY = "secret"

    def __init__(self):
        self.storage = {}

    def get(self, key: str) -> any:
        """
        Retrieve the value associated with the given key from the storage.

        Args:
            key (str): The key to retrieve the value for.

        Returns:
            The value associated with the key, or None if the key is not found.

        Original implementation:
            @classmethod
            def RedisWrapper.get(cls, key):
                '''
                Get the value associated with the given key from Redis.

                Args:
                    key (str): Redis key.

                Returns:
                    any: The retrieved value
                '''
        """
        return self.storage.get(key, None)

    def get_secure(self, key: str) -> any:
        """
        Retrieve the value associated with the given key from the storage.

        Args:
            key (str): The key to retrieve the value for.

        Returns:
            The value associated with the key, or None if the key is not found.

        Original implementation:
            @classmethod
            def RedisWrapper.get_secure(cls, key):
                '''
                Retrieves a secure value from Redis using the provided key.

                Args:
                    key (str): The key to retrieve the value from Redis.

                Returns:
                    any: The retrieved value if the signature matches.

                Raises:
                    SecurityError: If the signature doesn't match.
                '''
        """
        return self.storage.get(key, None)

    def set(self, key: str, value: any) -> None:
        """
        Set the value of a key in the storage.

        Args:
            key (str): The key to set.
            value (any): The value to set.

        Returns:
            None

        Original implementation:
            @classmethod
            def RedisWrapper.set(cls, key: str, value: any):
                '''
                Set the value associated with the given key in Redis.

                Args:
                    key (str): Redis key.
                    value (any): Value to be set. It can be of any type.
                '''
        """
        self.storage[key] = value

    def set_secure(self, key: str, value: any) -> None:  # pylint: disable=unused-argument
        """
        Set the value associated with the given key in the storage and generate an HMAC signature.

        Args:
            key (str): The key to set.
            value (any): The value to set.

        Returns:
            None

        Original implementation:
            @classmethod
            def RedisWrapper.set_secure(cls, key, value):
                '''
                Set the value associated with the given key in Redis and generate an HMAC signature.

                Args:
                    key (str): Redis key.
                    value (any): Value to be set. It can be of any type.
                '''
        """
        self.storage[key] = value

    def setex(self, key: str, value: any, expires: int) -> None:  # pylint: disable=unused-argument
        """
        Set the value of a key in the storage with an expiration time.

        Args:
            key (str): The key to set.
            value (any): The value to set.
            expires (int): The expiration time in seconds.

        Returns:
            None

        Original implementation:
            @classmethod
            def RedisWrapper.setex(cls, key: str, value: any, expires: int):
                '''
                Set the value associated with the given key in Redis with an expiration time.

                Args:
                    key (str): Redis key.
                    value (any): Value to be set. It can be of any type.
                    expires (int): Expiration time in seconds.
                '''
        """
        self.storage[key] = value

    def setex_secure(self, key: str, value: any, expires: int) -> None:  # pylint: disable=unused-argument
        """
        Set the value associated with the given key in the storage with an expiration time and generate an HMAC signature.

        Args:
            key (str): The key to set.
            value (any): The value to set.
            expires (int): The expiration time in seconds.

        Returns:
            None

        Original implementation:
            @classmethod
            def RedisWrapper.setex_secure(cls, key: str, value: any, expires: int):
                '''
                Set the value associated with the given key in Redis with an expiration time and generate an HMAC signature.

                Args:
                    key (str): Redis key.
                    value (any): Value to be set. It can be of any type.
                    expires (int): Expiration time in seconds.
                '''
        """
        self.storage[key] = value


class MockJsonSerializer:
    """
    A mock JSON serializer class that provides serialization and deserialization methods.
    """

    def serialize(self, obj: object) -> str:
        """
        Serialize the given object into a string representation.

        Args:
            obj: The object to be serialized.

        Returns:
            str: The serialized string representation of the object.

        Original implementation:
            @classmethod
            @abstractmethod
            def JsonSerializer.serialize(cls, obj: object):
                '''
                Serializes an object into a string representation.

                Args:
                    obj: The object to be serialized.

                Returns:
                    str: The serialized string representation of the object.
                '''
        """
        return str(obj)

    def deserialize(self, json_string: str) -> object:
        """
        Deserialize a JSON string into a Python object.

        Args:
            json_string (str): The JSON string to be deserialized.

        Returns:
            object: The deserialized Python object.

        Original implementation:
            @classmethod
            @abstractmethod
            def JsonSerializer.deserialize(cls, json_string: str):
                '''
                Deserialize a JSON string into an object of the class.

                Args:
                    json_string (str): The JSON string to deserialize.

                Returns:
                    object: The deserialized object.
                '''
        """
        return eval(json_string)  # pylint: disable=eval-used


@pytest.fixture
def mock_redis_wrapper():
    """
    Returns an instance of MockRedisWrapper.
    """
    return MockRedisWrapper()


@pytest.fixture
def mock_json_serializer():
    """
    Returns an instance of MockJsonSerializer.

    This function is used to create a mock JSON serializer object for testing purposes.

    Returns:
        MockJsonSerializer: An instance of the MockJsonSerializer class.
    """
    return MockJsonSerializer()
