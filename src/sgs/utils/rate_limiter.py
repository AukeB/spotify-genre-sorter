"""Spaces out requests to an external API."""

import time


class RateLimiter:
    """Makes the caller wait so that requests are at least min_interval seconds
    apart.

    Attributes:
        _min_interval (float): Smallest number of seconds between two requests.
        _last_request_at (float): Monotonic time of the most recent request.
    """

    def __init__(self, min_interval: float) -> None:
        """Creates a limiter with the given spacing.

        Args:
            min_interval (float): Smallest number of seconds between two
                requests.
        """
        self._min_interval = min_interval
        self._last_request_at = float("-inf")

    def wait(self) -> None:
        """Sleeps if needed, then records that a request is about to be made."""
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed

        if remaining > 0:
            time.sleep(remaining)

        self._last_request_at = time.monotonic()
