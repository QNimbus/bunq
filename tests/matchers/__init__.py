# tests/matchers/__init__.py

# pylint: disable=redefined-outer-name, unused-argument, unused-argument, unused-import, too-few-public-methods

# Standard library imports

# Third-party imports

# Local application/library imports


class String:
    """A class representing a string matcher."""

    def __eq__(self, other):
        return isinstance(other, str)
