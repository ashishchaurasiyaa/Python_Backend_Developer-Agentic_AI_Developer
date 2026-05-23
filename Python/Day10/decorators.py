"""
# Q2 — Decorator
# @retry(times=3, delay=1) banao
# Function fail ho toh retry karo
# 3 baar fail → original exception raise
"""

import time
import random
import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def retry(times=3,delay=1, backoff=2, max_delay=10, exceptions=(Exception,), jitter=True):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == times:
                        logger.error(f"Function {func.__name__} failed after {times} attempts.")
                        raise
                    sleep_time = current_delay
                    if jitter:
                        sleep_time += random.uniform(0, 0.5)
                    logger.warning(f"Attempt {attempt} failed. Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                    current_delay = min(current_delay * backoff, max_delay)
            raise last_exception
        return wrapper
    return decorator

@retry(times=4, delay=1)
def unstable_api():
    print("Calling unstable API...")
    return 1 / 0
unstable_api()
