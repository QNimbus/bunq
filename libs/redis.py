# redis.py

# Standard library imports
import os
import json
import functools

# Third-party imports
import json
import redis

# Local application/library imports
from libs.log import setup_logger
from libs.bunq_lib import BunqLib, MonetaryAccountBank

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))

# Get Redis connection details from environment variables
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)

# Initialize Redis client
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, db=0)


def custom_serializer(obj):
    # Check if the object has a 'to_json' method
    if hasattr(obj, "to_json") and callable(getattr(obj, "to_json")):
        # Add the object type to the JSON data
        # serialized_data = {"_object_type": obj.__class__.__name__, **obj.to_json()}
        serialized_data = obj.to_json()
        return serialized_data

    # Handle other types or raise error
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def custom_deserializer(data):
    # Check if 'data' is a dict and if so, loop over the keys
    if isinstance(data, dict):
        ret = {}
        for key, value in data.items():
            try:
                account_id = int(key)
                ret[account_id] = MonetaryAccountBank.from_json(value)
            except Exception as exc:
                pass
        return ret

    return data

def redis_memoize(func):
    """
    Decorator function that memoizes the result of a function using Redis as the cache.

    Args:
        func: The function to be memoized.

    Returns:
        The memoized function.

    Example:
        @redis_memoize
        def expensive_function(arg1, arg2):
            # Expensive computation
            return result
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        key_args = [arg.get_current_user().legal_name if isinstance(arg, BunqLib) else arg for arg in args]
        key_kwargs = {key: value.get_current_user().legal_name if isinstance(value, BunqLib) else value for key, value in kwargs.items()}

        key = f"{func.__name__}:{json.dumps({'args': key_args, 'kwargs': key_kwargs})}"

        # Check if the result is in Redis
        if (cached_result := r.get(key)) is not None:
            return json.loads(cached_result, object_hook=custom_deserializer)

        # Call the function and cache the result
        result = func(*args, **kwargs)

        r.set(key, json.dumps(result, default=custom_serializer))
        return result

    return wrapper
