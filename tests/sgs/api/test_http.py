"""Module for testing http.py"""

from unittest.mock import MagicMock, patch

import pytest

from sgs.api.http import get
from sgs.errors import RetryableApiError


def _response(status_code, headers=None):
    """Builds a fake requests.Response with the given status and headers.

    Args:
        status_code (int): The HTTP status code.
        headers (dict[str, str] | None): The response headers.
    """

    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}

    return response


# Testing the "get" function.


@patch("sgs.api.http.requests.get")
def test_get_returns_response_for_success(mock_get):
    """A normal response is returned as it is."""
    response = _response(200)
    mock_get.return_value = response

    result = get("https://api.example/items", headers={"A": "b"})

    assert result is response


@patch("sgs.api.http.requests.get")
def test_get_raises_rate_limited_with_retry_after(mock_get):
    """HTTP 429 raises RetryableApiError with the Retry-After seconds."""
    mock_get.return_value = _response(429, {"Retry-After": "12"})

    with pytest.raises(RetryableApiError) as error:
        get("https://api.example/items", headers={})

    assert error.value.retry_after == 12.0


@patch("sgs.api.http.requests.get")
def test_get_raises_rate_limited_without_usable_retry_after(mock_get):
    """HTTP 429 without a numeric Retry-After still raises, with no wait time."""
    mock_get.return_value = _response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})

    with pytest.raises(RetryableApiError) as error:
        get("https://api.example/items", headers={})

    assert error.value.retry_after is None


@patch("sgs.api.http.requests.get")
def test_get_raises_retryable_error_for_503(mock_get):
    """HTTP 503 is retried like a rate limit, since the service may be back shortly."""
    mock_get.return_value = _response(503)

    with pytest.raises(RetryableApiError) as error:
        get("https://api.example/items", headers={})

    assert error.value.status_code == 503

