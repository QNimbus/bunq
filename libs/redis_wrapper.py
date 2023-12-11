#!/usr/bin/env -S python -W ignore

# redis.py

# Standard library imports
import os
import hmac
import uuid
import pickle
import secrets
import hashlib
import inspect
import functools
from typing import Optional
from abc import ABC, abstractmethod


# Third-party imports
import redis

# Local application/library imports
from libs.exceptions import RedisMemoizeError, RedisMemoizeRuntimeError, SecurityError


# Get HMAC secret key from environment variable
REDIS_HMAC_SECRET_KEY = os.environ.get("REDIS_HMAC_SECRET_KEY", secrets.token_hex(32)).encode("utf-8")

# Get Redis connection details from environment variables
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)


class JsonSerializer(ABC):
    """
    A base class for serializing and deserializing objects into JSON strings.
    """

    @classmethod
    @abstractmethod
    def serialize(cls, obj):
        """
        Serializes an object into a JSON string.
        :param obj: The object to serialize.
        :return: A JSON string representation of the object.
        """

    @classmethod
    @abstractmethod
    def deserialize(cls, json_string):
        """
        Deserializes a JSON string back into an object.
        :param json_string: The JSON string to deserialize.
        :return: The deserialized object.
        """


def redis_memoize(expiration_time=600, secure=True, instance_identifier=None, serializer: JsonSerializer = None):
    """
    Decorator function for caching the result of a function using Redis.

    Args:
        expiration_time (int, optional): Expiration time in seconds for the cached result. Defaults to 60.
        secure (bool, optional): Flag indicating whether to use secure methods for caching. Defaults to True.
        instance_identifier (str, optional): Name of the method or property used to generate a unique identifier for the cached result. Defaults to None.
            If provided, this method or property will be accessed on the instance of the function's first argument. Defaults to None.
        serializer (JsonSerializer, optional): Serializer object used to serialize and deserialize the cached data. Defaults to None.

    Returns:
        function: Decorated function that caches its result using Redis.

    Raises:
        RedisMemoizeError: Thrown if HMAC secret key is not provided.

    Example usage:
        @redis_memoize(expiration_time=300, identifier_method='get_id')
        def get_data(user_id):
            # Function logic here
            return data
    """

    def decorator(func):
        # Throw exception if HMAC secret key is not provided
        if secure and not REDIS_HMAC_SECRET_KEY:
            raise RedisMemoizeError("HMAC secret key not provided")

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Check if the function is a method and has an instance
            if inspect.ismethod(func) or (len(args) > 0 and inspect.isclass(args[0].__class__)):
                instance = args[0]
                try:
                    # Check if instance identifier is callable and call it if it is
                    if instance_identifier and callable(getattr(instance, instance_identifier)):
                        instance_id = getattr(instance, instance_identifier)()
                    elif instance_identifier and hasattr(instance, instance_identifier):
                        instance_id = getattr(instance, instance_identifier)
                    else:
                        # Fallback to a default identifier (e.g., instance's `id`)
                        instance_id = id(instance)
                except Exception as exc:
                    raise RedisMemoizeRuntimeError(f"Failed to get instance identifier: {exc}") from exc

                key_suffix = f"{instance.__class__.__name__}:{instance_id}"
                key = f"{key_suffix}:{func.__name__}:{pickle.dumps((args[1:], kwargs))}"
            else:
                # It's a standalone function
                key_suffix = "standalone"
                key = f"{key_suffix}:{func.__name__}:{pickle.dumps((args, kwargs))}"

            if secure:
                # Try fetching the result from Redis using secure methods
                cached_data = RedisWrapper.get_secure(key)
            else:
                # Try fetching the result from Redis using non-secure methods
                cached_data = RedisWrapper.get(key)

            if cached_data is not None:
                # If a serialer is provided, deserialize the cached data
                if serializer is not None:
                    cached_data = serializer.deserialize(cached_data)

                return cached_data

            # Call the function and cache the result
            result = func(*args, **kwargs)

            # If a serialer is provided, serialize the result
            if serializer is not None:
                data_to_cache = serializer.serialize(result)
            else:
                data_to_cache = result

            if secure:
                # Cache the result using secure methods
                RedisWrapper.setex_secure(key=key, value=data_to_cache, expiration_time=expiration_time)
            else:
                # Cache the result using non-secure methods
                RedisWrapper.setex(key=key, value=data_to_cache, expiration_time=expiration_time)

            return result

        return wrapper

    return decorator


class RedisWrapper:
    """
    Wrapper class for Redis operations.
    """

    _client = None

    @classmethod
    def initialize(cls, host, port, password):
        """
        Initialize the Redis client.

        Args:
            host (str): Redis host.
            port (int): Redis port.
            password (str): Redis password.
        """
        if cls._client is None:
            cls._client = redis.Redis(host=host, port=port, password=password, db=0)

    @classmethod
    def _ensure_initialized(cls):
        """
        Ensures that the Redis client is initialized.

        Raises:
            RuntimeError: If the Redis client is not initialized.
        """
        if cls._client is None:
            raise RuntimeError("Redis client is not initialized. Call Redis.initialize() first.")

    @classmethod
    def generate_uuid(cls) -> str:
        """
        Generates a UUID using Redis.

        Returns:
            str: The generated UUID.
        """
        cls._ensure_initialized()
        return str(uuid.uuid4())

    @classmethod
    def get_id(cls, name: Optional[str] = "_id") -> str:
        """
        Generates an incrementing ID using Redis. Starts at 0 if the ID doesn't exist.

        Args:
            name (str, optional): The name of the ID. Defaults to "_id".

        Returns:
            str: The name of the ID
        """
        cls._ensure_initialized()
        return cls._client.incr(name=name)

    @classmethod
    def get_lock(cls, name: Optional[str] = "redis_lock", timeout: Optional[float] = None) -> bool:
        """
        Acquires a lock using Redis.

        Args:
            name (str, optional): The name of the lock. Defaults to "redis_lock".
            timeout (float, optional): The timeout in seconds. Defaults to 60.

        Returns:
            bool: True if the lock was acquired, False otherwise.
        """
        cls._ensure_initialized()
        return cls._client.lock(name=name, timeout=timeout)

    @classmethod
    def get(cls, key):
        """
        Get the value associated with the given key from Redis.

        Args:
            key (str): Redis key.

        Returns:
            any: The retrieved value
        """
        cls._ensure_initialized()
        value = cls._client.get(name=key)

        if value is None:
            return None

        return pickle.loads(value)

    @classmethod
    def get_secure(cls, key):
        """
        Retrieves a secure value from Redis using the provided key.

        Args:
            key (str): The key to retrieve the value from Redis.

        Returns:
            any: The retrieved value if the signature matches.

        Raises:
            SecurityError: If the signature doesn't match.
        """
        value = RedisWrapper.get(key)

        if value is None:
            return None

        result, stored_signature = pickle.loads(value)

        # Recompute the signature and compare
        computed_signature = hmac.new(REDIS_HMAC_SECRET_KEY, pickle.dumps(result), hashlib.sha256).hexdigest()
        if hmac.compare_digest(computed_signature, stored_signature):
            return result

        # Throw exception if the signature doesn't match
        raise SecurityError("Signature mismatch")

    @classmethod
    def set_secure(cls, key, value):
        """
        Set the value associated with the given key in Redis and generate an HMAC signature.

        Args:
            key (str): Redis key.
            value (any): Value to be set. It can be of any type.
        """
        # Generate HMAC signature
        signature = hmac.new(REDIS_HMAC_SECRET_KEY, pickle.dumps(value), hashlib.sha256).hexdigest()

        # Store the value and signature as a tuple
        RedisWrapper.set(key=key, value=pickle.dumps((value, signature)))

    @classmethod
    def setex_secure(cls, key, value, expiration_time):
        """
        Set the value associated with the given key in Redis with an expiration time and generate an HMAC signature.

        Args:
            key (str): Redis key.
            value (any): Value to be set. It can be of any type.
            expiration_time (int): Expiration time in seconds.
        """
        # Generate HMAC signature
        signature = hmac.new(REDIS_HMAC_SECRET_KEY, pickle.dumps(value), hashlib.sha256).hexdigest()

        # Store the value and signature as a tuple
        RedisWrapper.setex(key=key, expiration_time=expiration_time, value=pickle.dumps((value, signature)))

    @classmethod
    def set(cls, key, value):
        """
        Set the value associated with the given key in Redis.

        Args:
            key (str): Redis key.
            value (any): Value to be set. It can be of any type.
        """
        cls._ensure_initialized()
        cls._client.set(name=key, value=pickle.dumps(value))

    @classmethod
    def setex(cls, key, value, expiration_time):
        """
        Set the value associated with the given key in Redis with an expiration time.

        Args:
            key (str): Redis key.
            value (any): Value to be set. It can be of any type.
            expiration_time (int): Expiration time in seconds.
        """
        cls._ensure_initialized()
        cls._client.setex(name=key, time=expiration_time, value=pickle.dumps(value))

    @classmethod
    def delete(cls, key):
        """
        Delete the key and its associated value from Redis.

        Args:
            key (str): Redis key.
        """
        cls._ensure_initialized()
        cls._client.delete(name=key)

    @classmethod
    def flushdb(cls):
        """
        Delete all keys and their associated values from the current Redis database.
        """
        cls._ensure_initialized()
        cls._client.flushdb()

    # Helper methods

    @classmethod
    def log_request(cls, *, request_id: str) -> None:
        """
        Logs a request ID to Redis in a thread-safe manner.

        Args:
            request_id (str): The request ID to log.

        Returns:
            None
        """
        with RedisWrapper.get_lock("request_log_lock"):
            request_log = RedisWrapper.get("request_log") or []
            request_log.append(request_id)
            RedisWrapper.set("request_log", request_log)

    @classmethod
    def get_request_log(cls) -> list:
        """
        Gets the request log.

        Returns:
            list: The request log.
        """
        with RedisWrapper.get_lock("request_log_lock"):
            return RedisWrapper.get("request_log") or []

    @classmethod
    def get_processed_payments_for_user(cls, *, user_id: int) -> list[str]:
        """
        Gets the list of processed payments for a user.

        Args:
            user_id (int): The user ID.

        Returns:
            list: The list of processed payments for the user.
        """
        with RedisWrapper.get_lock("processed_payments_lock"):
            processed_payments: dict[int, list[str]] = RedisWrapper.get_secure("processed_payments") or {}

            if user_id not in processed_payments.keys():
                processed_payments[user_id] = []
                RedisWrapper.set_secure("processed_payments", processed_payments)

            return processed_payments[user_id]

    @classmethod
    def set_request_data(cls, *, request_id: str, data: dict) -> None:
        """
        Sets the data for a request.

        Args:
            request_id (str): The ID of the request.
            data (dict): The data to set.

        Returns:
            None
        """
        with RedisWrapper.get_lock("requests_lock"):
            with RedisWrapper.get_lock(f"request_lock::{request_id}"):
                RedisWrapper.set_secure(request_id, data)

    @classmethod
    def get_request_data(cls, *, request_id: str) -> Optional[dict]:
        """
        Gets the data for a request.

        Args:
            request_id (str): The ID of the request.

        Returns:
            Optional[dict]: The data for the request if it exists, None otherwise.
        """
        with RedisWrapper.get_lock("requests_lock"):
            with RedisWrapper.get_lock(f"request_lock::{request_id}"):
                return RedisWrapper.get_secure(request_id)

    @classmethod
    def remove_request_data(cls, *, request_id: str) -> None:
        """
        Removes the data for a request.

        Args:
            request_id (str): The ID of the request.

        Returns:
            None
        """
        with RedisWrapper.get_lock("requests_lock"):
            with RedisWrapper.get_lock(f"request_lock::{request_id}"):
                RedisWrapper.delete(request_id)

    @classmethod
    def get_all_request_data(cls) -> dict[str, dict]:
        """
        Gets the data for all requests.

        Returns:
            dict[str, dict]: The data for all requests.
        """
        request_log = RedisWrapper.get_request_log()
        with RedisWrapper.get_lock("requests_lock"):
            request_data = {request_id: RedisWrapper.get_secure(request_id) for request_id in request_log}

            return request_data

    @classmethod
    def register_payment(cls, *, user_id: int, payment_id: str) -> None:
        """
        Registers a payment as processed for a specific user.

        Args:
            user_id (int): The ID of the user.
            payment_id (str): The ID of the payment.

        Returns:
            None
        """
        with RedisWrapper.get_lock("processed_payments_lock"):
            processed_payments: dict[int, list[str]] = RedisWrapper.get_secure("processed_payments") or {}

            if user_id not in processed_payments.keys():
                processed_payments[user_id] = []

            processed_payments[user_id].append(payment_id)
            RedisWrapper.set_secure("processed_payments", processed_payments)

    @classmethod
    def unregister_payment(cls, *, user_id: int, payment_id: str):
        """
        Unregisters a payment as processed for a specific user.

        Args:
            user_id (int): The ID of the user.
            payment_id (str): The ID of the payment.
        """
        with RedisWrapper.get_lock("processed_payments_lock"):
            processed_payments: dict[int, list[str]] = RedisWrapper.get_secure("processed_payments") or {}

            if user_id not in processed_payments.keys():
                return

            if payment_id in processed_payments[user_id]:
                processed_payments[user_id].remove(payment_id)
                RedisWrapper.set_secure("processed_payments", processed_payments)


# Initialize Redis client
RedisWrapper.initialize(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)

if __name__ == "__main__":
    import argparse

    # Create the parser
    parser = argparse.ArgumentParser(description="Run a function from the script.", usage="redis.py {flushdb}")

    # Add arguments
    parser.add_argument("function", choices=["flushdb"], help="Specify the function to run. 'flushdb' for Redis.flushdb().")

    # Parse arguments
    args = parser.parse_args()

    # Check which function to call
    if args.function == "flushdb":
        RedisWrapper.flushdb()
    else:
        print("Invalid function.")
