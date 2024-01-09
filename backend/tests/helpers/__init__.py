# tests/helpers/__init__.py

# pylint: disable=redefined-outer-name, unused-argument, unused-argument, unused-import, too-few-public-methods

# Standard library imports
import sys

# Third-party imports

# Local application/library imports


def x_squared_function(x: int or float) -> int or float:
    """
    Returns the square of a given number. Function is used for testing purposes.

    Parameters:
    x (int or float): The number to be squared.

    Returns:
    int or float: The square of the input number.
    """
    return x * x


class InstanceMethodsClass:
    """
    A mock implementation of a class for testing purposes.
    """

    def __init__(self, instance_id: int):
        self.instance_id = instance_id

    def get_instance_id(self) -> int:
        """
        Get the instance ID.

        Returns:
            int: The instance ID.
        """
        return self.instance_id

    def set_instance_id(self, instance_id: int) -> None:
        """
        Set the instance ID.

        Args:
            id (int): The instance ID.
        """
        self.instance_id = instance_id

    @classmethod
    def classmethod_class_name(cls: object) -> str:
        """
        Get the class name.

        Args:
            cls (object): The class object.

        Returns:
            str: The class name.
        """
        return "MockInstance"

    @staticmethod
    def staticmethod_class_name() -> str:
        """
        Get the class name.

        Returns:
            str: The class name.
        """
        return "MockInstance"
