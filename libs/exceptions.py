# exceptions.py

# Standard library imports
# ...

# Third-party imports
# ...

# Local application/library imports
# ...


class RedisMemoizeError(Exception):
    """
    Exception raised for errors related to Redis memoization.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class RedisMemoizeRuntimeError(Exception):
    """
    Exception raised for errors related to Redis memoization during runtime.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class SecurityError(Exception):
    """Exception raised for security breaches such as data tampering.

    Attributes:
        message (str): Explanation of the security breach.
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class InvalidLogLevelError(Exception):
    """
    Raised when the provided log level is not a valid log level recognized by the logging module.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class MissingArgumentError(Exception):
    """
    Exception raised for missing required arguments.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class ConfigFileExistsError(Exception):
    """
    Exception raised when the config file already exists.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class PathNotWritableError(Exception):
    """
    Exception raised when the destination path is not writable.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message.strip()
        super().__init__(self.message)


class DateError(Exception):
    """Exception raised for errors in the date format or value.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class StatementNotFoundError(Exception):
    """Raised when the statement is not found.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ExportError(Exception):
    """Raised when there is an error in exporting the statement.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class StatementsRetrievalError(Exception):
    """Raised when an error occurs during the retrieval of statements.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class StatementDeletionError(Exception):
    """Raised when an error occurs during the deletion of statements.
    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class InvalidIPAddressError(Exception):
    """Exception raised when an invalid IP address is encountered.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class RuleProcessingError(Exception):
    """Exception raised for errors in the rule processing.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


# class InvalidCountError(ValueError):
#     """Raised when the provided count is not valid."""

#     pass


# class ScheduledPaymentsRetrievalError(Exception):
#     """Raised when an error occurs during the retrieval of scheduled payments."""

#     pass

# class FileExistsError(Exception):
#     """Raised when the file already exists and force parameter is False."""

#     pass


# class PathNotWritableError(Exception):
#     """Raised when the path is not writable."""

#     pass


# class InvalidDateFormatError(Exception):
#     """Raised when the date format is invalid."""

#     pass


# class InvalidStatementFormatError(Exception):
#     """Raised when the provided statement format is not valid."""

#     pass


# class InvalidRegionalFormatError(Exception):
#     """Raised when the provided regional format is not valid."""

#     pass
