"""Module for testing rate_limiter.py"""

from unittest.mock import MagicMock

from sgs.utils.rate_limiter import RateLimiter


# Testing the "wait" method from the "RateLimiter" class.


def test_wait_does_not_sleep_on_first_request(monkeypatch):
    """The first request goes out without waiting."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.rate_limiter.time.sleep", sleep)

    RateLimiter(min_interval=1.0).wait()

    sleep.assert_not_called()


def test_wait_sleeps_for_the_rest_of_the_interval(monkeypatch):
    """A second request right after the first waits for the interval to pass."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.rate_limiter.time.sleep", sleep)
    limiter = RateLimiter(min_interval=1.0)

    limiter.wait()
    limiter.wait()

    assert sleep.call_count == 1
    assert 0 < sleep.call_args.args[0] <= 1.0
