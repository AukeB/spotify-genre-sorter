"""Retries a function after a specific error, waiting between attempts.

The wait grows exponentially, up to a maximum. If the error says how long to
wait (RetryableApiError.retry_after), that time is used instead. A wait longer
than the maximum is not sleeps through: the error is raised at once, so the run
stops and can be resumed later.
"""

import functools
import logging
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

# P stands for the parameters of the wrapped function, so the decorator keeps
# the same arguments for type checkers.
P = ParamSpec("P")
# R stands for the return type of the wrapped function.
R = TypeVar("R")


def _delay_seconds(
    error: Exception,
    attempt: int,
    base_delay: float,
    backoff: float,
    max_delay: float,
) -> float | None:
    """Returns how long to wait before the next attempt, or None to give up.

    Args:
        error (Exception): The error the last attempt raised.
        attempt (int): The attempt that failed, starting at 1.
        base_delay (float): The first wait, in seconds.
        backoff (float): The factor each wait is multiplied by.
        max_delay (float): The longest wait allowed, in seconds.

    Returns:
        delay (float | None): Seconds to wait, or None if the wait the error
            asks for is longer than max_delay.
    """
    retry_after: float | None = getattr(error, "retry_after", None)

    if retry_after is None:
        exponential = base_delay * backoff ** (attempt - 1)
        delay = min(exponential, max_delay)
    elif retry_after > max_delay:
        delay = None
    else:
        delay = retry_after

    return delay


def retry(
    exceptions: type[Exception],
    max_attempts: int,
    base_delay: float,
    backoff: float,
    max_delay: float,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Creates a decorator that retries a function when it raises the given
    error.

    Args:
        exceptions (type[Exception]): The error class that triggers a retry.
        max_attempts (int): How many times the function is tried in total.
        base_delay (float): The first wait, in seconds.
        backoff (float): The factor each wait is multiplied by.
        max_delay (float): The longest wait allowed, in seconds.

    Returns:
        decorator (Callable): Decorator that wraps a function with the retry
            logic.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        """Wraps one function with the retry logic.

        Args:
            func (Callable[P, R]): The function to wrap.

        Returns:
            wrapper (Callable[P, R]): The wrapped function.
        """

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Calls the function, retrying when it raises the configured error.

            Args:
                *args: Positional arguments for the function.
                **kwargs: Keyword arguments for the function.

            Returns:
                result (R): What the function returns.
            """
            attempt = 1

            while True:
                try:
                    result = func(*args, **kwargs)
                except exceptions as error:
                    if attempt >= max_attempts:
                        raise

                    delay = _delay_seconds(
                        error, attempt, base_delay, backoff, max_delay
                    )

                    if delay is None:
                        raise

                    logger.warning(
                        "Attempt %d of %d failed (%s), waiting %.1f s before retrying",
                        attempt,
                        max_attempts,
                        error,
                        delay,
                    )
                    time.sleep(delay)
                    attempt += 1
                else:
                    return result

        return wrapper

    return decorator
