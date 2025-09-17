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

    # For MongoDB, convert to UTC while preserving the actual time
    # MongoDB stores dates as UTC, so we need to return a UTC datetime
    utc_time = italian_time.astimezone(pytz.UTC)

    return utc_time