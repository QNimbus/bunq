# date.py

# Standard library imports
import os
from datetime import date, datetime, timedelta

# Local application/library imports
from libs.logger import setup_logger
from libs.exceptions import DateError

# Setup logging
logger = setup_logger(__name__, os.environ.get("LOG_LEVEL", "INFO"))


def cap_date(date_obj: datetime) -> datetime:
    """
    Caps the given date to today's date if it is in the future, or to the minimum date if it is before the minimum date.

    Parameters:
    - date_obj: datetime
        The datetime object.

    Returns:
    - datetime
        The original datetime object if it is today or in the past, today's datetime object if the input date is in the future,
        or the minimum datetime object if the input date is before the minimum date.

    Raises:
    - ValueError: If the input date is not a datetime object.

    Examples:
    - cap_date(datetime(2023, 1, 1)) -> datetime(2023, 1, 1) (if today's date is after or equal to January 1, 2023)
    - cap_date(datetime(2023, 1, 1)) -> datetime(2023, 9, 30) (if today's date is September 30, 2023)
    - cap_date(datetime(1900, 1, 1)) -> datetime(1970, 1, 1) (if the minimum date is January 1, 1970)

    """
    if not isinstance(date_obj, datetime):
        raise ValueError("The input date is not a datetime object.")

    today = datetime.now()
    min_date = datetime(1970, 1, 1, 0, 0, 0)

    date_obj = max(date_obj, min_date)
    date_obj = min(date_obj, today)

    return date_obj


def week_to_dates(year: int, week_number: int) -> tuple[str, str]:
    """
    Get the start and end dates of the specified week number in a given year.

    Parameters:
    - year (int): The year.
    - week_number (int): The week number.

    Returns:
    - tuple[str, str]: A tuple containing the start and end date of the week in 'YYYY-MM-DD' format.

    Raises:
    - DateError: If the week number is not in the range 1-53.

    Example:
    >>> week_to_dates(2023, 40)
    ('2023-10-02', '2023-10-08')
    """
    if not 1 <= week_number <= 53:
        raise DateError(f"Week number must be between 1 and 53. Received {week_number}.")

    try:
        first_day_of_year = datetime(year, 1, 1)
        start_date = first_day_of_year + timedelta(days=(week_number * 7) - first_day_of_year.weekday())
        end_date = start_date + timedelta(days=6)

        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    except Exception as exc:
        raise DateError(f"An error occurred while calculating dates: {exc}") from exc


def date_to_week(date_str: str = None) -> tuple[int, int]:
    """
    Get the week number of a given date. Uses current date if no date string is provided.

    Parameters:
    - date_str (str, optional): The date string in 'YYYY-MM-DD' format. Defaults to current date.

    Returns:
    - tuple[int, int]: The year and week number.

    Raises:
    - DateError: If the date string is not in the correct format or an invalid date.

    Example:
    >>> date_to_week('2023-10-04')
    (2023, 40)
    >>> date_to_week()
    # Returns the year and week number of the current date.
    """
    try:
        if date_str is None:
            date_str = date.today().isoformat()

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return (date_obj.isocalendar()[0], date_obj.isocalendar()[1])

    except ValueError as exc:
        raise DateError(f"The date string '{date_str}' is not in 'YYYY-MM-DD' format or is an invalid date.") from exc
