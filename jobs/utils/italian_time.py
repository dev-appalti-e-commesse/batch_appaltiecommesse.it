from datetime import datetime
from typing import overload, Literal
import pytz


@overload
def get_italian_time() -> datetime: ...

@overload
def get_italian_time(only_date_string: Literal[True]) -> str: ...

@overload
def get_italian_time(only_date_string: Literal[False], full_date_format: Literal[True]) -> str: ...


def get_italian_time(only_date_string: bool = False, full_date_format: bool = False) -> datetime | str:
    """
    Gets the current time in Italy's timezone (UTC+1/UTC+2 depending on DST)
    The returned datetime object is offset-aware and suitable for MongoDB storage
    Includes milliseconds for more precise timestamping

    Args:
        only_date_string: If True, returns date as string in DDMMYYYY format
        full_date_format: If True, returns date as string in DD/MM/YYYY_HH:mm.SSS format

    Returns:
        datetime object or formatted date string
    """
    # Get current time in Italian timezone
    italy_tz = pytz.timezone('Europe/Rome')
    italian_time = datetime.now(italy_tz)

    if only_date_string:
        return italian_time.strftime('%d%m%Y')

    if full_date_format:
        # Format with milliseconds
        return italian_time.strftime('%d/%m/%Y_%H:%M.%f')[:-3]  # Remove last 3 digits to get milliseconds

    # For MongoDB, we create a UTC datetime with Italian time values
    # This replicates the TypeScript behavior of creating a Date.UTC with Italian time components
    # Note: This creates a datetime that appears to be Italian time but is marked as UTC
    year = italian_time.year
    month = italian_time.month
    day = italian_time.day
    hour = italian_time.hour
    minute = italian_time.minute
    second = italian_time.second
    microsecond = italian_time.microsecond

    # Create a datetime with Italian time values
    naive_italian = datetime(year, month, day, hour, minute, second, microsecond)

    # Mark it as UTC (even though the values are actually Italian time)
    # This matches the TypeScript behavior
    utc_marked = pytz.UTC.localize(naive_italian)

    return utc_marked