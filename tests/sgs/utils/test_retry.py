"""Module for testing retry.py"""

from unittest.mock import MagicMock

import pytest

from sgs.errors import RetryableApiError
from sgs.utils.retry import retry


def _flaky(failures, result="ok"):
    """Builds a function that raises RetryableApiError the given number of times, then returns result."""
    state = {"calls": 0}

    def func():
        state["calls"] += 1

        if state["calls"] <= failures:
            raise RetryableApiError(None)

        return result

    return func


# Testing the "retry" decorator.


def test_retry_returns_result_after_failures(monkeypatch):
    """A function that fails twice and then succeeds returns its result."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)
    wrapped = retry(RetryableApiError, max_attempts=5, base_delay=1.0, backoff=2.0, max_delay=60.0)(_flaky(2))

    result = wrapped()

    assert result == "ok"
    assert [call.args[0] for call in sleep.call_args_list] == [1.0, 2.0]


def test_retry_gives_up_after_max_attempts(monkeypatch):
    """After the last attempt fails, the error is raised."""
    monkeypatch.setattr("sgs.utils.retry.time.sleep", MagicMock())
    wrapped = retry(RetryableApiError, max_attempts=3, base_delay=1.0, backoff=2.0, max_delay=60.0)(_flaky(10))

    with pytest.raises(RetryableApiError):
        wrapped()


def test_retry_caps_exponential_wait_at_max_delay(monkeypatch):
    """A wait that would grow past max_delay is capped at max_delay."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)
    wrapped = retry(RetryableApiError, max_attempts=4, base_delay=10.0, backoff=10.0, max_delay=30.0)(_flaky(3))

    wrapped()

    assert [call.args[0] for call in sleep.call_args_list] == [10.0, 30.0, 30.0]


def test_retry_uses_retry_after_from_error(monkeypatch):
    """When the error says how long to wait, that time is used."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)
    calls = {"count": 0}

    def func():
        calls["count"] += 1

        if calls["count"] == 1:
            raise RetryableApiError(7.0)

        return "ok"

    wrapped = retry(RetryableApiError, max_attempts=3, base_delay=1.0, backoff=2.0, max_delay=60.0)(func)

    assert wrapped() == "ok"
    assert sleep.call_args.args[0] == 7.0


def test_retry_raises_at_once_when_retry_after_exceeds_max_delay(monkeypatch):
    """A wait longer than max_delay stops the run without sleeping."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)

    def func():
        raise RetryableApiError(3600.0)

    wrapped = retry(RetryableApiError, max_attempts=5, base_delay=1.0, backoff=2.0, max_delay=300.0)(func)

    with pytest.raises(RetryableApiError):
        wrapped()

    sleep.assert_not_called()


def test_retry_does_not_retry_other_errors(monkeypatch):
    """Errors that are not the configured class are raised straight away."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)

    def func():
        raise ValueError("not a rate limit")

    wrapped = retry(RetryableApiError, max_attempts=5, base_delay=1.0, backoff=2.0, max_delay=60.0)(func)

    with pytest.raises(ValueError):
        wrapped()

    sleep.assert_not_called()


def test_retry_never_waits_less_than_backoff_when_server_says_zero(monkeypatch):
    """A Retry-After of 0 still waits for the normal backoff instead of retrying at once."""
    sleep = MagicMock()
    monkeypatch.setattr("sgs.utils.retry.time.sleep", sleep)
    calls = {"count": 0}

    def func():
        calls["count"] += 1

        if calls["count"] == 1:
            raise RetryableApiError(0.0)

        return "ok"

    wrapped = retry(RetryableApiError, max_attempts=3, base_delay=2.0, backoff=2.0, max_delay=60.0)(func)

    assert wrapped() == "ok"
    assert sleep.call_args.args[0] == 2.0
