# redis_memoizer.py

# Standard library imports
import sys
import types
import pickle
import inspect
import functools
from typing import Optional
from abc import ABC, abstractmethod

# Third-party imports

# Local application/library imports
from libs.redis_wrapper import RedisWrapper
from libs.exceptions import RedisMemoizeError, RedisMemoizeRuntimeError

# Import logger
from libs import logger  # pylint: disable=ungrouped-imports,unused-import


class JsonSerializer(ABC):
    """
    A base class for serializing and deserializing objects into JSON strings.
    """

    @classmethod
    @abstractmethod
    def serialize(cls, obj: object) -> str:
        """
        Serializes an object into a string representation.

        Args:
            obj: The object to be serialized.

        Returns:
            str: The serialized string representation of the object.
        """

    @classmethod
    @abstractmethod
    def deserialize(cls, json_string: str) -> object:
        """
        Deserialize a JSON string into an object of the class.

        Args:
            json_string (str): The JSON string to deserialize.

        Returns:
            object: The deserialized object.

        """


class RedisMemoizer:  # pylint: disable=too-few-public-methods
    """
    RedisMemoizer is a class that provides caching functionality using Redis as the backend.

    Args:
        expires (int): The expiration time in seconds for the cached result. Default is 600 seconds.
        secure (bool): Flag indicating whether to use secure caching. Default is True.
        instance_identifier (str): An identifier for the instance (if applicable). Default is None.
        serializer (Optional[JsonSerializer]): The serializer to use for serializing and deserializing the cached data. Default is None.

    Raises:
        RedisMemoizeError: If secure caching is enabled but REDIS_HMAC_SECRET_KEY is not provided.

    Methods:
        generate_key(func: callable, args: tuple, kwargs: dict, instance_identifier: str) -> str:
            Generate a unique key for caching based on the function, arguments, and instance identifier.

        is_method_with_instance(func: callable, args: tuple) -> bool:
            Check if the given function is a method with an instance or a class method.

        get_instance_id(instance: object, instance_identifier: str) -> any:
            Get the instance ID based on the provided instance and instance identifier.

        fetch_from_cache(key: str, secure: bool) -> any:
            Fetches a value from the cache based on the given key.

        deserialize_data(cached_data: any, serializer: Optional[JsonSerializer]) -> any:
            Deserialize the cached data using the provided serializer.

        cache_result(key: str, result: any, serializer: Optional[JsonSerializer], secure: bool, expires: int) -> None:
            Cache the result using the specified key and options.

        decorator(self, func) -> callable:
            Decorator function that can be used to memoize a function.

    """

    def __init__(self, expires=600, secure=True, instance_identifier=None, serializer=None):
        self.expires = expires
        self.secure = secure
        self.instance_identifier = instance_identifier
        self.serializer = serializer
        if secure and not RedisWrapper.REDIS_HMAC_SECRET_KEY:
            raise RedisMemoizeError("HMAC secret key not provided")

    @staticmethod
    def generate_key(func: callable, args: tuple, kwargs: dict, instance_identifier: str) -> str:
        """
        Generate a unique key for caching based on the function, arguments, and instance identifier.

        Args:
            func (callable): The function to be cached.
            args (tuple): The positional arguments passed to the function.
            kwargs (dict): The keyword arguments passed to the function.
            instance_identifier (str): An identifier for the instance (if applicable).

        Returns:
            str: The generated key for caching.
        """
        if RedisMemoizer.is_method(func):
            instance = args[0]
            instance_id = RedisMemoizer.get_instance_id(instance, instance_identifier)
            key_suffix = f"{instance.__class__.__name__}:{instance_id}"
            return f"{key_suffix}:{func.__name__}:{pickle.dumps((args[1:], kwargs))}"

        key_suffix = "standalone"
        return f"{key_suffix}:{func.__name__}:{pickle.dumps((args, kwargs))}"

    @staticmethod
    def get_all_classes(module):
        """
        Retrieves all classes from a given module and its submodules.

        Args:
            module (module): The module to inspect.

        Returns:
            set: A set of all classes found.
        """
        classes = set()
        for _, obj in inspect.getmembers(module):
            if inspect.isclass(obj):
                classes.add(obj)
        return classes

    @staticmethod
    def is_method(func: callable) -> bool:
        """
        Check if the given function is a method belonging to a class or a class instance (object),
        or if it's a standalone function. It also checks for staticmethods.

        Args:
            func (callable): The function to check.

        Returns:
            bool: True if the function is a method (instance, class, or static method), False otherwise.
        """
        if inspect.ismethod(func):
            return True

        func_name = func.__name__
        try:
            module = sys.modules[func.__globals__["__name__"]]
        except KeyError:
            module = None

        all_classes = set()
        if module:
            all_classes.update(RedisMemoizer.get_all_classes(module))

        for cls in all_classes:
            if func_name in cls.__dict__:
                obj_member = cls.__dict__[func_name]
                return isinstance(obj_member, types.FunctionType)

        return False

    @staticmethod
    def is_standalone_function(func: callable) -> bool:
        """
        Check if the given function is a standalone function (not a method).

        Args:
            func (callable): The function to check.

        Returns:
            bool: True if the function is a standalone function, False otherwise.
        """
        return not RedisMemoizer.is_method(func)

    @staticmethod
    def get_instance_id(instance: object, instance_identifier: str) -> any:
        """
        Get the instance ID based on the provided instance and instance identifier.

        Args:
            instance (object): The instance object.
            instance_identifier (str): The identifier for the instance.

        Returns:
            any: The instance ID.
        """
        if instance_identifier and callable(getattr(instance, instance_identifier, None)):
            return getattr(instance, instance_identifier)()
        if instance_identifier and hasattr(instance, instance_identifier):
            return getattr(instance, instance_identifier)
        return id(instance)

    @staticmethod
    def fetch_from_cache(key: str, secure: bool) -> any:
        """
        Fetches a value from the cache based on the given key.

        Args:
            key (str): The key to fetch the value for.
            secure (bool): Indicates whether the value should be fetched securely.

        Returns:
            any: The fetched value from the cache.
        """
        if secure:
            return RedisWrapper.get_secure(key)
        return RedisWrapper.get(key)

    @staticmethod
    def deserialize_data(cached_data: any, serializer: Optional[JsonSerializer]) -> any:
        """
        Deserialize the cached data using the provided serializer.

        Args:
            cached_data (any): The data to be deserialized.
            serializer (Optional[JsonSerializer]): The serializer to be used for deserialization.

        Returns:
            any: The deserialized data.
        """
        if serializer is not None:
            return serializer.deserialize(cached_data)
        return cached_data

    @staticmethod
    def cache_result(key: str, result: any, serializer: Optional[JsonSerializer], secure: bool, expires: int) -> None:
        """
        Cache the result using the specified key and options.

        Args:
            key (str): The key to use for caching.
            result (any): The result to be cached.
            serializer (Optional[JsonSerializer]): The serializer to use for serializing the result.
            secure (bool): Flag indicating whether to use secure caching.
            expires (int): The expiration time in seconds for the cached result.
        """
        data_to_cache = serializer.serialize(result) if serializer else result

        if secure:
            RedisWrapper.setex_secure(key=key, value=data_to_cache, expires=expires)
        else:
            RedisWrapper.setex(key=key, value=data_to_cache, expires=expires)

    def decorator(self, func):
        """
        Decorator function that caches the result of the decorated function using RedisMemoizer.

        Args:
            func: The function to be decorated.

        Returns:
            The decorated function.
        """

        @functools.wraps(func)
        def wrapper(*args: any, **kwargs: any) -> any:
            try:
                key = RedisMemoizer.generate_key(func, args, kwargs, self.instance_identifier)
                cached_data = RedisMemoizer.fetch_from_cache(key, self.secure)

                if cached_data is not None:
                    return RedisMemoizer.deserialize_data(cached_data, self.serializer)

                # Call the function and cache the result
                result = func(*args, **kwargs)
                RedisMemoizer.cache_result(key, result, self.serializer, self.secure, self.expires)
                return result
            except pickle.PicklingError as error:
                args_str = ", ".join([str(arg) for arg in args])
                error_message = f"Error while pickling data: ({args_str})"
                logger.error(error_message)
                raise RedisMemoizeRuntimeError(error_message) from error

        return wrapper


def redis_memoize(expires=600, secure=True, instance_identifier=None, serializer=None) -> callable:
    """
    Decorator function that memoizes the result of a function using Redis as the caching mechanism.

    Args:
        expires (int): The expiration time in seconds for the cached result. Default is 600 seconds.
        secure (bool): Flag indicating whether to use a secure connection to Redis. Default is True.
        instance_identifier (str): An optional identifier to distinguish different instances of the memoizer.
        serializer (callable): A function used to serialize the cached result. Default is None.

    Returns:
        callable: The decorator function that can be used to memoize other functions.
    """
    memoizer = RedisMemoizer(expires, secure, instance_identifier, serializer)
    return memoizer.decorator
