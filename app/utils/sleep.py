"""
Sleep utilities for farming
"""

import pytz
from datetime import datetime, timedelta


def get_sleep_until(minutes: int = None, seconds: int = None) -> datetime:
    """Get future datetime after sleeping for specified minutes/seconds"""
    duration = timedelta()
    
    if minutes is not None:
        duration += timedelta(minutes=minutes)
    
    if seconds is not None:
        duration += timedelta(seconds=seconds)
    
    return datetime.now(pytz.UTC) + duration


async def verify_sleep(value: datetime) -> bool:
    """Verify if sleep time has passed"""
    if value is None:
        return True
    
    current_time = datetime.now(pytz.UTC)
    
    # If value already has timezone, use it, otherwise consider UTC
    if value.tzinfo is None:
        sleep_until = value.replace(tzinfo=pytz.UTC)
    else:
        sleep_until = value.astimezone(pytz.UTC)
    
    if sleep_until > current_time:
        return False
    return True

